import pandas as pd

def read_xml(xml_file):
    df = pd.read_xml(xml_file, xpath='.//list')
    return df

dartCodes=read_xml('dart_codes/CORPCODE.xml')
corp_code=dict(zip(dartCodes['corp_name'],dartCodes['corp_code']))
stock_code=dict(zip(dartCodes['corp_name'],dartCodes['stock_code']))


print(dartCodes.head(1))