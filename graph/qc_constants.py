fuseki_hostname = "137.184.139.216"
fuseki_username = "root"
fuseki_port = 3030



question_texts = {
	0: "How many Clayton civil cases involve someone who also appeared as a Clayton criminal defendant?",
	1: "How many Clayton civil eviction cases involve someone who also appeared as a Clayton criminal defendant?",
	2: "For Clayton civil eviction cases that involve someone who also appeared as a Clayton criminal defendant, what is the average number of days between the end of the eviction case and the start of the criminal case?",
	3: "For Clayton civil eviction cases that involve someone who was also sentenced in a Clayton criminal case, what is the average number of days between the end of the sentence and the start of the eviction case?",
	4: "What is the average number of days between booking dates and first hearings in Fulton?",
	5: "What is the average number of days between Fulton hearings, by case?",
	6: "What is the average number of days between Fulton hearings, by charge?",
	7: "What is the average number of days between Fulton hearings, by NIBRS drug code?",
	8: lambda query: query, # TODO
	9: "What is the count of APD/Clayton charges, by NIBRS drug code?",
	10: "What is the count of APD/Clayton charges, by race code?",
	11: "What is the length in days of Clayton cases, by NIBRS offense code?",
	12: "What is the length in days of Clayton cases, by NIBRS drug code?",
	13: "What is the length in docket entries of Clayton cases, by NIBRS offense code?",
	14: "What is the length in docket entries of Clayton cases, by NIBRS drug code?",
	15: lambda query: query, # TODO
	16: "How many PACER cases have an application to proceed in forma pauperis?",
	17: "How many PACER cases per year have an application to proceed in forma pauperis?",
	18: "How many PACER cases have a granted application to proceed in forma pauperis?",
	19: "What percentage of PACER applications to proceed in forma pauperis are granted, by judge?",
	20: "What percentage of PACER applications to proceed in forma pauperis are granted, by court?",
	21: lambda query: query, # TODO
	22: lambda query: query, # TODO
	23: lambda query: query, # TODO
	24: lambda query: query, # TODO
	25: lambda query: query, # TODO
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



def helper_2(results):
	for row in results:
		pass # TODO

question_helpers = {
	0: lambda results: len(set([row['civil_case']['value'] for row in results])),
	1: lambda results: len(set([row['civil_case'] for row in results if row['civil_type'] == 'Patho'])),
	2: helper_2
	# TODO finish the rest
}
