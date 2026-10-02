import re
from datetime import datetime
from collections import Counter

import pandas as pd
from dateutil.relativedelta import relativedelta



fuseki_hostname = "137.184.139.216"
fuseki_username = "root"
fuseki_port = 3030

filters_description = '''
**************************************************************************************
***      These QC results were generated from a small test dataset, which was      ***
***    filtered down from the full dataset according to the following criteria:    ***
**************************************************************************************

- apd: arrests whose nc:ActivityDate is between Jan–Mar 2015 inclusive
- clayton: cases whose case id contains "23-c" and whose court category code is "COC" 
- fulton: charges whose case has an attached booking whose nc:StartDate is in Jan 2021
- pacer: cases in Alaska (akd) or the Northern Mariana Islands (nmid)
'''



question_texts = {
	0: "How many Clayton civil cases involve a party who also appeared as a Clayton criminal defendant?",
	1: "How many Clayton civil eviction cases involve a party who also appeared as a Clayton criminal defendant?",
	2: "For Clayton civil eviction cases that involve a party who also appeared as a Clayton criminal defendant, across all civil-case/criminal-case pairs, what is the average number of days from the end of the eviction case to the start of the criminal case?",
	3: "For Clayton civil cases that involve a party who was also sentenced to prison time in a Clayton criminal case, across all civil-case/criminal-sentence pairs, what is the average number of days from the end of the sentence to the start of the case?",
	4: "In Fulton, what is the average number of days from a booking date associated with a case to that case's first docket entry involving the booked party, excluding negative date differences?",
	5: "What is the average number of days between Clayton/Fulton/PACER hearings, by case?",
	6: "What is the average number of days between Clayton/Fulton/PACER hearings, by NIBRS offense category?",
	7: "What is the average number of days between Clayton/Fulton/PACER hearings, by NIBRS drug code?",
	8: "How many people were being held in the Fulton County Jail at any time on 1 Feb 2021?", # may change in the future based on danny_4_date in run_graph_qc
	9: "What is the total count of APD/Clayton drug charges, by NIBRS drug code?",
	10: "What is the total count of APD drug charges, by race code?",
	11: "What is the average length in days of closed Clayton cases, by NIBRS offense category?",
	12: "What is the average length in days of closed Clayton cases, by NIBRS drug code?",
	13: "What is the average length in docket entries of Clayton cases, by NIBRS offense category?",
	14: "What is the average length in docket entries of Clayton cases, by NIBRS drug code?",
	15: None, # not needed for the data explorer right now
	16: "How many PACER cases have an application to proceed in forma pauperis?",
	17: "How many PACER cases have an application to proceed in forma pauperis, by starting year of the case?",
	18: "How many PACER cases have a granted application to proceed in forma pauperis?",
	19: "What percentage of PACER applications to proceed in forma pauperis are granted, by granting judge?",
	20: "What percentage of PACER applications to proceed in forma pauperis are granted, by court?",
	21: "What percentage of PACER cases with nature of suit 110 (Insurance) settle?", # may change in the future based on pacer_2_nos in run_graph_qc
	22: "What is the average number of days from the start of a PACER NOS-110 case to the start of settlement?", # may change in the future based on pacer_2_nos in run_graph_qc
	23: "What is the average number of days from the start of a PACER NOS-110 case to the start of settlement, by court?", # may change in the future based on pacer_2_nos in run_graph_qc
	24: "What percentage of PACER NOS-110 cases contain a private individual, i.e. a party whose name has been redacted?", # may change in the future based on pacer_2_nos in run_graph_qc
	25: "On average, in settling PACER NOS-110 cases with a private individual, does settlement begin sooner or later than in settling NOS-110 cases with only unredacted parties?", # may change in the future based on pacer_2_nos in run_graph_qc
	26: "What is the average number of motions to dismiss in PACER cases with nature of suit beginning with 44 (civil rights cases)?",
	27: "What is the average number of motions to dismiss in PACER NOS-44X cases, by starting year of the case?",
	28: "What percentage of motions to dismiss in PACER NOS-44X cases are granted?",
	29: "What percentage of motions to dismiss in PACER NOS-44X cases are granted, by starting year of the case?",
	30: "What percentage of PACER cases with nature of suit 463/530/535/540/550/555 (habeas corpus cases) are dismissed?",
	31: "Which court sees the most PACER NOS-463/530/535/540/550/555 cases?",
	32: "Which court sees the least PACER NOS-463/530/535/540/550/555 cases?",
	33: "What percentage of PACER cases have a motion to seal?",
	34: "Which nature of suit has the highest percentage of PACER cases with a motion to seal?",
	35: "What is the distribution of PACER motions to seal across natures of suit?",
	36: "What is the distribution of PACER motions to seal across courts?"
}
ALL = list(question_texts.keys())
APD = [k for k,v in question_texts.items() if v and 'apd' in v.lower()]
CLAYTON = [k for k,v in question_texts.items() if v and 'clayton' in v.lower()]
FULTON = [k for k,v in question_texts.items() if v and 'fulton' in v.lower()]
PACER = [k for k,v in question_texts.items() if v and 'pacer' in v.lower()]

# keys are question numbers, and values are n such that qc_query_n.sparql is the query that provides the data needed to answer the question
question_queries = {
	0: 0, 1: 0,
	2: 1, 3: 1,
	4: 2,
	5: 3, 6: 3, 7: 3,
	8: 4,
	9: 5, 10: 5,
	11: 6, 12: 6, 13: 6, 14: 6,
	15: 7,
	16: 8, 17: 8, 18: 8, 19: 8, 20: 8,
	21: 9, 22: 9, 23: 9, 24: 9, 25: 9,
	26: 10, 27: 10, 28: 10, 29: 10,
	30: 11, 31: 11, 32: 11,
	33: 12, 34: 12, 35: 12, 36: 12
}

# natural-language descriptions of data nuances that an LLM might not be able to deduce from the question texts and the scales schema
# each key is a piece of information, and each value is a tuple of question numbers for which the information may apply
domain_knowledge = {
	'Unless otherwise specified, questions and domain knowledge mentioning "APD" are referring to arrests etc tied to the Atlanta Police Department agency, distinguishable by its j:OrganizationCategoryNLETSCode value of "PD."': APD,
	'Unless otherwise specified, questions and domain knowledge mentioning "Clayton" are referring to cases etc whose j:CourtName includes "Court of Clayton County, Georgia."': CLAYTON,
	'Unless otherwise specified, questions and domain knowledge mentioning "Fulton" are referring to cases/bookings/etc tied to the Fulton County Jail facility, whose nc:PhysicalAddress is "901 Rice St NW, Atlanta, GA 30318."': FULTON,
	'Unless otherwise specified, questions and domain knowledge mentioning "PACER" are referring to cases etc whose j:CourtName starts with "District Court" and ends with the name of a U.S. state or territory.': PACER,
	'Although the SCALES graph includes no explicit datasource/provenance data and (as per RDF conventions) can make no formal guarantees about meaning encoded in URIs, APD arrest URIs are informally identifiable by the substring "ga-atlanta-pd" in situations where multi-hop join paths might create performance issues.': APD,
	'Although the SCALES graph includes no explicit datasource/provenance data and (as per RDF conventions) can make no formal guarantees about meaning encoded in URIs, Clayton case URIs are informally identifiable by the substring "ga-clayton" in situations where multi-hop join paths might create performance issues.': CLAYTON,
	'Although the SCALES graph includes no explicit datasource/provenance data and (as per RDF conventions) can make no formal guarantees about meaning encoded in URIs, Fulton booking URIs are informally identifiable by the substring "ga-fulton" in situations where multi-hop join paths might create performance issues.': FULTON,
	'Although the SCALES graph includes no explicit datasource/provenance data and (as per RDF conventions) can make no formal guarantees about meaning encoded in URIs, PACER case URIs are informally identifiable with the regex "^[a-z]{2,3}d;;" in situations where multi-hop join paths might create performance issues.': PACER,
	'The literal values that can appear as an object of j:CourtCategoryCode are as follows: "SUP" (superior courts), "MAG" (magistrate courts), "COC" (state courts); each value pertains to both the civil and criminal sides of the court at that level.': CLAYTON,
	'All cases in the SCALES graph are either civil or criminal, and not both; the former are typed as scales:CivilCase and the latter as scales:CriminalCase.': CLAYTON+FULTON+PACER,
	'Unless otherwise specified, fields beginning "scales:Idb" are unreliable and should not be used.': ALL,
	'The only way to determine whether two parties correspond to the same underlying entity is by checking whether they are linked to the same scales:DisambiguatedEntity value.': [0, 1, 2, 3],
	'Questions mentioning "defendants" are referring to parties typed as j:CaseDefendantParty; for those parties, j:ParticipantRoleCategoryText may rarely point to finer-grained party-role data, but that data is irrelevant when answering these questions.': [0, 1, 2],
	'Questions mentioning "eviction cases" are referring to cases with a nc:CaseSubCategoryText value of "Patho."': [1, 2],
	'The question phrasing "number of days from X to Y" permits both positive and negative values, whereas the phrasing "number of days between" implies the absolute value of the time delta.': [2, 3, 4, 5, 6, 7, 22, 23],
	'Questions mentioning "sentenced to prison time" are referring to parties with a j:Sentence whose j:SentenceDescriptionText is "serve," which should be construed to start on the case\'s nc:EndDate and end after the ISO 8601 duration specified in the sentence\'s j:TermDuration.': [3],
	'Questions mentioning "first docket entry" are referring to the entry that is chronologically earliest.': [4],
	'For questions requesting aggregation "by X," nodes with null grouping keys (e.g. cases with a null offense-code value when grouping is "by offense code") should be dropped, with two exceptions: (1) when the grouping key is "nature of suit," cases with no nature of suit should receive the key "criminal," and (2) when the grouping key is a demographic variable (e.g. sex, race, ethnicity), rows with a null key should be grouped into a null bucket.': [5, 6, 7, 9, 10, 11, 12, 13, 14, 19, 20, 23, 27, 29],
	'For questions requesting aggregation "by X," nodes with multiple grouping keys (e.g. cases with multiple offense-code values across multiple charges when grouping is "by offense code") should be counted in the multiple buckets corresponding to the multiple codes.': [5, 6, 7, 9, 10, 11, 12, 13, 14, 19, 20, 23, 27, 29],
	'A missing end date or release date implies that the node with the missing date (e.g. case, booking) was still ongoing at the time the underlying data was collected.': [8],
	'Questions and domain knowledge mentioning "hearings" are referring to docket entries.': [5, 6, 7],
	'For questions mentioning "days between hearings," time deltas with length 0 are permissible.': [5, 6, 7],
	'For questions mentioning "days between hearings," entries with identical date and text should be deduplicated.': [5, 6, 7],
	'For questions mentioning "average number of days between hearings, by [offense code | drug code]," the deltas should be computed within each case and then pooled across all cases matching a given offense code or drug code, as opposed to computing an average for each case and then averaging the averages.': [6, 7],
	'For questions requesting multiple datasources (e.g. "Clayton/Fulton/PACER"), results should be pooled rather than split up by datasource.': [5, 6, 7, 9],
	'Questions and domain knowledge mentioning "offense category" or "offense code" are referring to nibrs:OffenseUCRCode.': [6, 11, 13],
	'Questions mentioning "drug charges" are referring to charges with a j:DrugCategoryCode attached in some way.': [9, 10],
	'For questions mentioning case length, cases with no nc:EndDate should be dropped.': [11, 12, 13, 14],
	'For questions mentioning "in forma pauperis," scales:IfpLabel should be used rather than scales:OntologyLabel.': [16, 17, 18, 19, 20],
	'For questions mentioning "in forma pauperis," the scales:IfpLabel value "IFP_APPLICATION" is unreliable and should be dropped; in lieu of that label, IFP applications can be inferred from the presence of other labels (i.e. IFP_GRANT, IFP_DENY, and IFP_OTHER), with each such label implying the existence of an underlying application.': [16, 17, 18, 19, 20],
	'Questions mentioning "court" should use j:CaseCourt only, rather than attempting to deduce additional information about secondary courts from which or to which a case was transferred.': [20, 23, 31, 32, 36],
	'Although the SCALES graph (as per RDF conventions) can make no formal guarantees about meaning encoded in URIs, for questions referring to a "scales:OntologyLabel value" or a specific kind of case event (e.g. motion to dismiss, motion to seal), pending the addition of literal strings corresponding to scales:OntologyLabel URIs, the natural-language name of the case event denoted by such a URI can be determined by taking the substring following the final forward slash in the URI.': [21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 33, 34, 35, 36],
	'Questions mentioning "settlement" are referring to docket entries with a scales:OntologyLabel value of "settlement"; settlement should be construed to begin on the date of the first docket entry with such a label, and settlement begins at most once per case.': [21, 22, 23, 24, 25],
	'Questions mentioning "nature of suit" or "NOS" are referring to nc:CaseSubCategoryText, which for PACER cases stores nature of suit as a string containing a numerical code and a standardized description.': [21, 22, 23, 24, 25, 34],
	'Questions mentioning "redacted" parties are referring to parties whose nc:EntityName contains the substring "SCALES-Party-Hash."': [24, 25],
	'Questions asking for a percentage of motions to dismiss that are granted should be construed as asking for a numerator counting docket entries with a scales:OntologyLabel value of "granting_motion_to_dismiss" and a denominator counting entries with a value of "motion_to_dismiss".': [28, 29],
	'Questions mentioning case dismissal are referring to cases with a docket entry whose scales:OntologyLabel value matches the regex "(?!motion).*dismiss".': [30]
}

# updated 9/28/2026; not sure if we'll ever need to use this info in other code, but it seemed as good a place as any to keep it
questions_validated = (0, 4, 5, 6, 7)

_duration_re = re.compile(r'^P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?$')
_to_datetime = lambda x: datetime.strptime(str(x), '%Y-%m-%d')

def _parse_iso_duration(duration):
	years, months, days = (int(g) if g else 0 for g in _duration_re.match(duration).groups())
	return relativedelta(years=years, months=months, days=days)



def helper_query3(results, key):
	if key not in ('case', 'nibrs', 'drug'):
		raise Exception('unexpected key', key)
	dates_all, nibrs_to_cid, drug_to_cid = {}, {}, {}
	for row in results:
		cid, nibrs, drug = row.get('case'), row.get('nibrs'), row.get('drug')
		if not cid:
			continue
		cid = cid.split('/')[-1]
		dates_all.setdefault(cid, set()).add(f"{row['date']} | {row['text']}")
		if not pd.isna(nibrs):
			nibrs_to_cid.setdefault(nibrs, set()).add(cid)
		if not pd.isna(drug):
			drug_to_cid.setdefault(drug, set()).add(cid)
	diffs_all = {}
	for cid, dates in dates_all.items():
		dates = sorted([_to_datetime(date.split(' | ')[0]) for date in dates])
		if len(dates)>1:
			for i in range(len(dates)-1):
				diffs_all.setdefault(cid, []).append((dates[i+1]-dates[i]).days)
	if key == 'case':
		return pd.DataFrame([(case, sum(diffs)/len(diffs)) for case, diffs in diffs_all.items()], columns=[key, 'avg_days_diff'])
	else:
		dict_of_interest = nibrs_to_cid if key == 'nibrs' else drug_to_cid # assumes potential key values are 'case', 'nibrs', 'drug'
		tuples = []
		for k, cids in dict_of_interest.items():
			diffs = []
			for cid in cids:
				diffs += diffs_all.get(cid) or []
			tuples.append((k, sum(diffs)/len(diffs)))
		return pd.DataFrame(tuples, columns=[key, 'avg_days_diff'])

def helper_query6(results, length_type, group_key):
	case_lengths, key_to_cids = {}, {}
	for row in results:
		cid = row['case']
		if cid not in case_lengths:
			case_lengths[cid] = (_to_datetime(row['end_date'])-_to_datetime(row['start_date'])).days \
				if length_type == 'days' else row['entry_count']
		key_to_cids.setdefault(row[group_key], set()).add(cid)
	tuples = [(key, sum(case_lengths[cid] for cid in cids)/len(cids)) for key, cids in key_to_cids.items()]
	return pd.DataFrame(tuples, columns=[group_key, f'avg_length_{length_type}'])

def helper_query8(results, group_key):
	df = pd.DataFrame(results).dropna(subset=[group_key])
	non_application = df[~df['ifp_label'].str.contains('IFP_APPLICATION')]
	granted = non_application['ifp_label'].str.contains('IFP_GRANT')
	return {k: float(v) for k, v in (granted.groupby(non_application[group_key]).mean()*100).items()}

def helper_query9(results):
	df = pd.DataFrame(results)
	meta = df.drop_duplicates('case').set_index('case')[['court', 'start_date']]
	settlement_date = df.dropna(subset=['entry_date']).groupby('case')['entry_date'].min()
	redacted = df.groupby('case')['party_name'].apply(lambda names: names.str.startswith('SCALES-Party-Hash-').any())
	case_df = meta.assign(settlement_date=settlement_date, has_redacted_party=redacted)
	case_df['days_to_settlement'] = (pd.to_datetime(case_df['settlement_date']) - pd.to_datetime(case_df['start_date'])).dt.days
	return case_df

def helper_query10(results):
	df = pd.DataFrame(results)
	case_years = df.drop_duplicates('case').set_index('case')['year'].str[:4]
	dismissals = df[df['label'].str.contains('motion_to_dismiss')].assign(year=lambda d: d['case'].map(case_years))
	return case_years, dismissals

def helper_query12(results):
	df = pd.DataFrame(results)
	sealed = df.groupby('case')['label'].apply(lambda labels: labels.str.contains('motion_to_seal').any())
	meta = df.drop_duplicates('case').set_index('case')[['nos', 'court']]
	return meta.join(sealed.rename('sealed'))



def helper_question2(results):
	civil = [row for row in results if 'civil' in row['case_id'] and row.get('case_types') == 'Patho']
	criminal = [row for row in results if 'civil' not in row['case_id']]
	diffs = [(_to_datetime(crim['start_date'])-_to_datetime(civ['end_date'])).days for civ in civil for crim in criminal if crim['party'] == civ['party']]
	return sum(diffs)/len(diffs)

def helper_question3(results):
	civil = [row for row in results if 'civil' in row['case_id']]
	criminal = [row for row in results if 'civil' not in row['case_id']]
	diffs = []
	for civ in civil:
		for crim in criminal:
			if crim['party'] != civ['party'] or pd.isna(crim['types']) or pd.isna(crim['end_date']):
				continue
			durations, types = crim['durations'].split(), crim['types'].split()
			inds_of_interest = [i for i,x in enumerate(types) if x == 'serve'] # if x == 'None' or len(types) == 1]
			if len(inds_of_interest) > 1: # != 1:
				raise Exception(f"ambiguous sentence data: {durations}, {types}")
			if inds_of_interest:
				sentence_end = _to_datetime(crim['end_date']) + _parse_iso_duration(durations[inds_of_interest[0]])
				diffs.append((_to_datetime(civ['start_date']) - sentence_end).days)
	return sum(diffs)/len(diffs)

def helper_question25(results):
	case_df = helper_query9(results)
	redacted_avg = case_df[case_df['has_redacted_party']]['days_to_settlement'].mean()
	unredacted_avg = case_df[~case_df['has_redacted_party']]['days_to_settlement'].mean()
	# conclusion = 'more quickly' if redacted_avg < unredacted_avg else 'more slowly' if redacted_avg > unredacted_avg else 'about the same'
	return {'private_individual_avg_days_to_settlement': float(redacted_avg), 'unredacted_only_avg_days_to_settlement': float(unredacted_avg)} # 'conclusion': conclusion

def helper_question27(results):
	case_years, dismissals = helper_query10(results)
	totals = case_years.groupby(case_years).size()
	counts = dismissals.groupby('year').size().reindex(totals.index, fill_value=0)
	return {year: float(avg) for year, avg in (counts/totals).items()}

def helper_question29(results):
	_, dismissals = helper_query10(results)
	granted = dismissals['label'].str.contains('granting')
	pct_by_year = granted.groupby(dismissals['year']).mean()*100
	return {year: float(pct) for year, pct in pct_by_year.items()}



question_helpers = {
	0: lambda results: len(set([row['civil_case'] for row in results])),
	1: lambda results: len(set([row['civil_case'] for row in results if row['civil_type'] == 'Patho'])),
	2: helper_question2,
	3: helper_question3,
	4: lambda results: sum([(_to_datetime(row['first_hearing_date'])-_to_datetime(row['booking_date'])).days for row in results])/len(results),
	5: lambda results: helper_query3(results, 'case'),
	6: lambda results: helper_query3(results, 'nibrs'),
	7: lambda results: helper_query3(results, 'drug'),
	8: lambda results: len(results),
	9: lambda results: Counter([row['drug_code'] for row in results]).most_common(),
	10: lambda results: Counter([row['race'] if 'race' in row else None for row in results]).most_common(),
	11: lambda results: helper_query6(results, 'days', 'nibrs'),
	12: lambda results: helper_query6(results, 'days', 'drug'),
	13: lambda results: helper_query6(results, 'entries', 'nibrs'),
	14: lambda results: helper_query6(results, 'entries', 'drug'),
	15: None, # not needed for the data explorer right now
	16: lambda results: len(set([row['case'] for row in results if row['ifp_label'] != 'IFP_APPLICATION'])),
	17: lambda results: Counter([x[1] for x in set([(row['case'], row['year'].split('-')[0]) for row in results if row['ifp_label'] != 'IFP_APPLICATION'])]).most_common(),
	18: lambda results: len(set([row['case'] for row in results if row['ifp_label'] == 'IFP_GRANT'])),
	19: lambda results: helper_query8(results, 'ifp_judge'),
	20: lambda results: helper_query8(results, 'court'),
	21: lambda results: float(helper_query9(results)['settlement_date'].notna().mean()*100),
	22: lambda results: float(helper_query9(results)['days_to_settlement'].mean()),
	23: lambda results: {court: float(avg) for court, avg in helper_query9(results).groupby('court')['days_to_settlement'].mean().items()},
	24: lambda results: float(helper_query9(results)['has_redacted_party'].mean()*100),
	25: helper_question25,
	26: lambda results: len(helper_query10(results)[1]) / len(helper_query10(results)[0]),
	27: helper_question27,
	28: lambda results: float(helper_query10(results)[1]['label'].str.contains('granting').mean()*100),
	29: helper_question29,
	30: lambda results: len(set(row['case'] for row in results if re.search(r'(?i)attribute/(?!motion).*dismiss', row['label'])))*100/len(set(row['case'] for row in results)),
	31: lambda results: Counter({row['case']: row['court'] for row in results}.values()).most_common(1)[0][0],
	32: lambda results: Counter({row['case']: row['court'] for row in results}.values()).most_common()[-1][0],
	33: lambda results: float(helper_query12(results)['sealed'].mean()*100),
	34: lambda results: helper_query12(results).groupby('nos')['sealed'].mean().pipe(lambda pct: list(pct[pct == pct.max()].index)),
	35: lambda results: Counter(helper_query12(results).query('sealed')['nos'].fillna('criminal')).most_common(),
	36: lambda results: Counter(helper_query12(results).query('sealed')['court']).most_common()
}
