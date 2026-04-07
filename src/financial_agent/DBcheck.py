import sqlite3
import os

def inspect_sqlite_structure(db_path):
    """SQLite 데이터베이스의 테이블 목록과 각 테이블의 컬럼 구조를 분석합니다."""
    
    if not os.path.exists(db_path):
        print(f"🚨 오류: '{db_path}' 파일을 찾을 수 없습니다.")
        return

    # 1. DB 연결
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 2. 데이터베이스 내의 모든 테이블 이름 가져오기 (시스템 테이블인 sqlite_sequence 등은 제외)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = cursor.fetchall()

        if not tables:
            print("데이터베이스 안에 만들어진 테이블이 없습니다 (빈 DB입니다).")
            return

        print(f"📊 데이터베이스 '{db_path}' 내부 구조 분석 결과")
        print("=" * 60)

        # 3. 각 테이블을 순회하며 구조 뜯어보기
        for table_name_tuple in tables:
            table_name = table_name_tuple[0]
            print(f"📌 테이블명: [ {table_name} ]")
            
            # PRAGMA 명령어로 테이블의 컬럼 정보 상세 조회
            cursor.execute(f"PRAGMA table_info('{table_name}');")
            columns = cursor.fetchall()
            
            # 컬럼 정보 출력 포맷팅
            print(f"  {'순번':<4} | {'컬럼명':<15} | {'데이터 타입':<10} | {'Null 허용':<8} | {'기본키(PK)':<8}")
            print("-" * 60)
            
            for col in columns:
                cid = col[0]           # 컬럼 고유 번호
                name = col[1]          # 컬럼명
                ctype = col[2]         # 데이터 타입 (INTEGER, TEXT 등)
                notnull = "No" if col[3] else "Yes" # 0이면 Null 허용, 1이면 Not Null
                pk = "PK" if col[5] else ""         # 1이면 Primary Key
                
                print(f"  {cid:<4} | {name:<15} | {ctype:<10} | {notnull:<8} | {pk:<8}")
            
            print("=" * 60)

    except sqlite3.Error as e:
        print(f"🚨 SQLite 에러 발생: {e}")
    
    finally:
        # 4. 작업이 끝나면 반드시 연결 종료
        cursor.close()
        conn.close()

# ---------------------------------------------------------
# 실행 부분
# ---------------------------------------------------------
if __name__ == "__main__":
    # 사용자님의 SQLite 데이터베이스 파일 경로를 입력하세요.
    # 예: "my_data.db" 또는 "./data/stock_data.db"
    DB_PATH = "C:/Users/huira/Desktop/projectr/projectr/projectr/data/FS.db" 
    
    inspect_sqlite_structure(DB_PATH)