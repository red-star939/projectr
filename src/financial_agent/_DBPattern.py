import FS_to_SQL
import conSQL

db = conSQL.FS()
df = FS_to_SQL.FSpreproc("data/Financial_Statement/SK하이닉스/SK하이닉스.json")

# 들어오는 데이터가 회사별, 보고서 종류별, 계정별, 연도별 하나만 존재하도록 subset 설정
subset_keys = ['corp_code', 'fs_div', 'sj_div', 'account_nm', 'target_year']
db.to_sql("SK하이닉스", df, subset=subset_keys)
print("DB 생성이 완료되었습니다!")
print(db.search_sql("SK하이닉스"))
db.close()