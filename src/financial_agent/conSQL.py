import sqlite3
import json
import pandas as pd
import os

class FS():
    def __init__(self, init_sectors=True):
        '''
        데이터베이스 접근 계층(Data Access Layer) 역할의 클래스.
        FS.db에 접근하고 제어하는 모든 쿼리는 반드시 이 클래스를 거쳐야 합니다.
        '''
        db_name = "data/FS.db"
        self.db_name = db_name
        
        # 폴더 생성 로직
        os.makedirs(os.path.dirname(db_name), exist_ok=True)
        self.conn = sqlite3.connect(db_name)
        
        # 마스터 테이블 자동 생성 및 초기화 체크
        if init_sectors:
            self._init_sector_table()
        
    def _init_sector_table(self):
        """
        FS.db 내부에 상위 계층 역할을 할 'SECTORS' 마스터 메타데이터 테이블을 생성합니다.
        (회사 이름, 섹터) 쌍을 보관하며, 이미 존재하면 생성하지 않습니다.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS SECTORS (
                    corp_name TEXT PRIMARY KEY,
                    sector TEXT
                )
            """)
            self.conn.commit()
            
            # 테이블이 비어있는지 갯수로 확인하여 최초 로드 수행
            cursor.execute("SELECT COUNT(*) FROM SECTORS")
            count = cursor.fetchone()[0]
            if count == 0:
                print("💡 SECTORS 테이블이 비어있습니다. Sector 모듈을 경유하여 계층 정보를 자동 초기화합니다...")
                from src.financial_agent import Sector
                Sector._load_sectors()
        except Exception as e:
            print(f"SECTORS 테이블 생성 중 오류 발생: {e}")

    def insert_sector_map(self, df):
        """
        Sector.py에서 파싱한 전수 데이터프레임(corp_name, sector)을 인자로 받아
        SECTORS 마스터 테이블을 일괄 세팅/업데이트합니다.
        """
        try:
            # 중복 데이터는 replace 덮어쓰기 형태로 최신화
            df.to_sql(con=self.conn, name="SECTORS", if_exists="replace", index=False)
            return True
        except Exception as e:
            print(f"SECTORS 데이터 삽입 도중 에러 발생: {e}")
            return False

    def get_sector(self, corp_name):
        """
        회사 이름이 주어졌을 때 내부 테이블을 조회하여 상위 계층인 Sector 이름을 반환합니다.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT sector FROM SECTORS WHERE corp_name=?", (corp_name,))
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                return "기타(DB없음)"
        except sqlite3.Error as e:
            print(f"섹터 검색 중 에러 발생: {e}")
            return "오류"

    def get_corps_by_sector(self, sector):
        """
        특정 섹터 이름이 주어지면 해당 섹터에 포함된 모든 회사 리스트를 가져옵니다.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT corp_name FROM SECTORS WHERE sector=?", (sector,))
            results = cursor.fetchall()
            return [row[0] for row in results] if results else []
        except sqlite3.Error as e:
            print(f"회사 목록 검색 중 에러 발생: {e}")
            return []

    # ==========================================
    # 아래부터는 파이프라인/재무제표 데이터 통상 관리
    # ==========================================
    def to_sql(self, table_name, df, if_exists="append", index=False, subset=None):
        try:
            if if_exists == "append":
                if subset is None:
                    subset = ['source', 'report_type', 'corp_code', 'fs_div', 'sj_div', 'account_nm', 'target_year']
                    
                cursor = self.conn.cursor()
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
                if cursor.fetchone() is not None:
                    existing_df = pd.read_sql(f"SELECT * FROM '{table_name}'", self.conn)
                    combined_df = pd.concat([existing_df, df], ignore_index=True)
                    
                    valid_subset = [col for col in subset if col in combined_df.columns]
                    if valid_subset:
                        combined_df.drop_duplicates(subset=valid_subset, keep='last', inplace=True)
                    
                    combined_df.to_sql(con=self.conn, name=table_name, if_exists="replace", index=index)
                    return True
            
            df.to_sql(con=self.conn, name=table_name, if_exists=if_exists, index=index)
            return True
        except Exception as e:
            print(f"sql 저장 도중 에러 발생: {e}")
            return False
            
    def has_table(self, table_name):
        try:
            cursor = self.conn.cursor()
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
            return cursor.fetchone() is not None
        except sqlite3.Error as e:
            return False

    def search_sql(self, q):
        try:
            conn = sqlite3.connect(self.db_name)
            query = f"SELECT * FROM '{q}'"
            result_df = pd.read_sql_query(query, conn)
            return result_df
        except sqlite3.Error as e:
            print(f"SQL 실행 중 에러 발생: {e}")
            return None
        finally:
            if 'conn' in locals() and conn:
                conn.close()
    
    def close(self):
        self.conn.close()