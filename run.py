"""로컬 서버를 실행한다. Ctrl+C로 종료."""
import argparse
import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="과제 마감 대시보드")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"\n과제 마감 대시보드: http://127.0.0.1:{args.port}\n종료: Ctrl+C\n", flush=True)
    uvicorn.run("app:app", host="127.0.0.1", port=args.port)
