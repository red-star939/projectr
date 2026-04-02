import sqlite3
import json
import pandas as pd
import os

class FS():
    def __init__(self):
        '''
        .to_sql(table_name, df, if_exists="replace", index=False)
        해당 sql db에 df 넣기

        close() db 강제로 닫기. 코드 마지막에 꼭 넣기?
        '''

        db_name = "data/FS.db"
        self.db_name=db_name
        self.conn = sqlite3.connect(db_name)
        
    def to_sql(self, table_name, df, if_exists="append", index=False, subset=None):
        try:
            if if_exists == "append":
                # 테이블이 이미 존재하는지 확인
                cursor = self.conn.cursor()
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
                if cursor.fetchone() is not None:
                    existing_df = pd.read_sql(f"SELECT * FROM '{table_name}'", self.conn)
                    combined_df = pd.concat([existing_df, df], ignore_index=True)
                    combined_df.drop_duplicates(subset=subset, keep='last', inplace=True)
                    combined_df.to_sql(con=self.conn, name=table_name, if_exists="replace", index=index)
                    return True
            
            df.to_sql(con=self.conn, name=table_name, if_exists=if_exists, index=index)
            return True
        except Exception as e:
            print(f"sql 저장 도중 에러 발생: {e}")
            return None    
    def search_sql(self, q):
        """
        DB 이름과 SQL 쿼리를 입력받아 결과를 Pandas DataFrame으로 반환합니다.
        """
        try:
            # 1. DB 연결 (통로 열기)
            conn = sqlite3.connect(self.db_name)
            
            # 2. 쿼리 실행 및 결과를 DataFrame으로 즉시 변환
            query = f"SELECT * FROM '{q}'"
            result_df = pd.read_sql_query(query, conn)
            
            return result_df

        except sqlite3.Error as e:
            print(f"SQL 실행 중 에러 발생: {e}")
            return None
            
        finally:
            # 3. 작업이 끝났거나 에러가 났어도 무조건 문을 닫음
            if conn:
                conn.close()
    
    def close(self):
        self.conn.close()