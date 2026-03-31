import FS_to_SQL
import conSQL

db = conSQL.FS()
df = FS_to_SQL.FSpreproc("data/Financial_Statement/SK하이닉스/SK하이닉스.json")
db.to_sql("SK하이닉스", df)
print("DB 생성이 완료되었습니다!")
print(db.search_sql("SK하이닉스"))
db.close()