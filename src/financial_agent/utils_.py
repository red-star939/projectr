import pandas as pd

def read_xml(xml_file):
    df = pd.read_xml(xml_file, xpath='.//list')
    return df

dartCodes=read_xml('src/financial_agent/CORPCODE.xml')
corp_code=dict(zip(dartCodes['corp_name'],dartCodes['corp_code']))
stock_code=dict(zip(dartCodes['corp_name'],dartCodes['stock_code']))

def call_corp_code(corp):
    return corp_code[corp]


def call_stock_code(corp):
    return stock_code[corp]