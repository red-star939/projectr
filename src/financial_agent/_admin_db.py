import os
import os
import sys
from pathlib import Path

# FS.db의 절대 경로 조회를 위한 BASE_DIR 확보
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# config 모듈(루트 위치) 임포트를 위한 시스템 경로 추가
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

# key.env로부터 읽은 삭제 전용 패스워드 로드
from config import DB_PASSWORD
from src.financial_agent import conSQL
DB_PATH = BASE_DIR / "data" / "FS.db"

def clear_fs_db():
    """
    FS.db 파일 내의 모든 테이블(SECTORS, 개별 회사 데이터 등)을 안전하게 삭제하고 내용을 완전히 비웁니다.
    """
    print("==================================================")
    print("⚠️ [관리자 권한] FS.db 데이터 완전 초기화를 시작합니다.")
    print("==================================================")
    
    if not DB_PASSWORD:
        print("❌ 오류: 삭제 권한 비밀번호(DB_PASSWORD)가 환경 변수(key.env)에 설정되어 있지 않습니다.")
        print("key.env 파일에 DB_PASSWORD=비밀번호 를 추가해주세요.")
        return
    
    user_input = input("정말 FS.db의 모든 내용을 삭제하시겠습니까? (삭제 비밀번호 입력): ")
    
    # 보안 강화를 위한 비밀번호 대조
    if user_input != DB_PASSWORD:
        print("❌ 비밀번호가 일치하지 않습니다. 작업이 안전하게 취소되었습니다.")
        return

    if not DB_PATH.exists():
        print("❌ 오류: FS.db 파일이 지정된 경로에 없습니다.")
        return

    try:
        # DB 연결 (conSQL 기능 활용)
        db = conSQL.FS(init_sectors=False)
        cursor = db.conn.cursor()

        # 데이터베이스 내의 존재하는 모든 테이블 이름 가져오기
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        if not tables:
            print("💡 FS.db는 현재 완전히 비어있습니다. (테이블 0개)")
            db.close()
            return

        print(f"\n🗑️ 총 {len(tables)}개의 테이블 DROP 연산을 시작합니다...")

        # 모든 테이블 완전 삭제
        count = 0
        for table_name in tables:
            t_name = table_name[0]
            # SQLite 내부 관리 테이블 무시
            if t_name != 'sqlite_sequence':
                cursor.execute(f"DROP TABLE '{t_name}'")
                count += 1
                
        # DROP 연산 후 디스크 용량 회수 (가장 중요)
        cursor.execute("VACUUM;")
        db.conn.commit()
        db.close()

        print(f"\n✅ 초기화 완료: {count}개의 테이블이 안전하게 삭제되었으며 디스크 공간이 회수되었습니다.")
        print("💡 팁: 시스템을 다시 가동 시 conSQL 등을 통해 필요한 테이블이 백지 상태에서 자동으로 재생성됩니다.")

    except Exception as e:
        print(f"❌ 초기화 도중 치명적인 에러가 발생했습니다: {e}")

if __name__ == "__main__":
    clear_fs_db()
