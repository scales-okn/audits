from datetime import datetime
from collections import Counter

import pandas as pd



fuseki_hostname = "137.184.139.216"
fuseki_username = "root"
fuseki_port = 3030

filters_description = '''
**********************************************************************************
***    These QC results were generated from a small test dataset, which was    ***
***  filtered down from the full dataset according to the following criteria:  ***
**********************************************************************************

- apd: arrests whose NC.ActivityDate is between Jan–Mar 2015 inclusive
- clayton: cases for which the case id contains "23-c"
- fulton: charges whose NC.StartDate is in Jan 2021
- pacer: cases in Alaska district court (akd)
'''



question_texts = {
	0: "How many Clayton civil cases involve someone who also appeared as a Clayton criminal defendant?",
	1: "How many Clayton civil eviction cases involve someone who also appeared as a Clayton criminal defendant?",
	2: "For Clayton civil eviction cases that involve someone who also appeared as a Clayton criminal defendant, what is the average number of days between the end of the eviction case and the start of the criminal case?",
	3: "For Clayton civil eviction cases that involve someone who was also sentenced in a Clayton criminal case, what is the average number of days between the end of the sentence and the start of the eviction case?",
	4: "What is the average number of days between booking dates and first hearings in Fulton?",
	5: "What is the average number of days between Clayton/Fulton/PACER hearings, by case?",
	6: "What is the average number of days between Clayton/Fulton/PACER hearings, by NIBRS offense category?",
	7: "What is the average number of days between Clayton/Fulton/PACER hearings, by NIBRS drug code?",
	8: "What was the Fulton County Jail population on 1 Feb 2021?", # depends on danny_4_date in run_graph_qc
	9: "What is the total count of APD/Clayton drug charges, by NIBRS drug code?",
	10: "What is the total count of APD drug charges, by race code?",
	11: "What is the length in days of Clayton cases, by NIBRS offense category?",
	12: "What is the length in days of Clayton cases, by NIBRS drug code?",
	13: "What is the length in docket entries of Clayton cases, by NIBRS offense category?",
	14: "What is the length in docket entries of Clayton cases, by NIBRS drug code?",
	15: None, # TODO (not needed for the data explorer right now)
	16: "How many PACER cases have an application to proceed in forma pauperis?",
	17: "How many PACER cases per year have an application to proceed in forma pauperis?",
	18: "How many PACER cases have a granted application to proceed in forma pauperis?",
	19: "What percentage of PACER applications to proceed in forma pauperis are granted, by judge?",
	20: "What percentage of PACER applications to proceed in forma pauperis are granted, by court?",
	21: "What percentage of PACER Fair Labor Standards Act (FLSA) cases settle?", # depends on pacer_2_nos in run_graph_qc, which i changed from nos code 830 because that code didn't produce results for the test set
	22: "What is the average number of days that elapse in a PACER FLSA case before settlement starts?", # depends on pacer_2_nos in run_graph_qc
	23: "What is the average number of days that elapse in a PACER FLSA case before settlement starts, by court?", # depends on pacer_2_nos in run_graph_qc
	24: "What percentage of PACER FLSA cases contain a non-corporate party?", # depends on pacer_2_nos in run_graph_qc
	25: "On average, do PACER FLSA cases with a non-corporate party settle more quickly or more slowly than FLSA cases with only corporate parties?", # depends on pacer_2_nos in run_graph_qc
	26: "What is the average number of motions to dismiss in PACER civil rights cases?",
	27: "What is the average number of motions to dismiss in PACER civil rights cases, by year?",
	28: "What percentage of motions to dismiss in PACER civil rights cases are granted?",
	29: "What percentage of motions to dismiss in PACER civil rights cases are granted, by year?",
	30: "What percentage of PACER habeas-corpus cases are dismissed?",
	31: "Which court sees the most PACER habeas-corpus cases?",
	32: "Which court sees the least PACER habeas-corpus cases?",
	33: "What percentage of PACER cases have a motion to seal?",
	34: "Which nature of suit has the highest percentage of PACER cases with a motion to seal?",
	35: "What is the distribution of PACER motions to seal across natures of suit?",
	36: "What is the distribution of PACER motions to seal across courts?"
}

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



_to_datetime = lambda x: datetime.strptime(str(x), '%Y-%m-%d')

def helper_query3(results, key):
	dates_all = {}
	for row in results:
		category = row.get(key, {}).get('value')
		if not category:
			continue
		if '/' in category:
			category = category.split('/')[-1]
		if category not in dates_all:
			dates_all[category] = set()
		dates_all[category].add(f'{row['date']['value']} | {row['text']['value']}')
	diffs_all = {}
	for category, dates in dates_all.items():
		dates = sorted([_to_datetime(x.split(' | ')[0]) for x in dates])
		if len(dates)>1:
			if category not in diffs_all:
				diffs_all[category] = []
			for i in range(len(dates)-1):
				diffs_all[category].append((dates[i+1]-dates[i]).days)
	return pd.DataFrame([(category, sum(diffs)/len(diffs)) for category, diffs in diffs_all.items()], columns=[key, 'avg_days_diff'])

def helper_question29(results):
	years = {}
	for row in results:
		year = row['date']['value'].split('-')[0]
		if year not in years:
			years[year] = {'granted': 0, 'all': 0}
		years[year]['granted' if 'granting' in row['label']['value'] else 'all'] += 1
	for year in years:
		years[year] = years[year]['granted']*100/years[year]['all']
	return years

question_helpers = {
	0: lambda results: len(set([row['civil_case']['value'] for row in results])),
	1: lambda results: len(set([row['civil_case'] for row in results if row['civil_type'] == 'Patho'])),
	4: lambda results: sum([(_to_datetime(row['firstHearingDate']['value'])-_to_datetime(row['bookingDate']['value'])).days for row in results])/len(results),
	5: lambda results: helper_query3(results, 'case'),
	6: lambda results: helper_query3(results, 'nibrs'),
	7: lambda results: helper_query3(results, 'drug'),
	9: lambda results: Counter([row['drugCode']['value'] for row in results]).most_common(),
	10: lambda results: Counter([row['race']['value'] if 'race' in row else None for row in results]).most_common(),
	16: lambda results: len(set([x['case']['value'] for x in results])),
	17: lambda results: Counter([row['start_date']['value'].split('-')[0] for row in results]).most_common(),
	28: lambda results: len([row for row in results if 'granting' in row['label']['value']])*100/len([row for row in results if 'granting' not in row['label']['value']]),
	29: helper_question29
}
