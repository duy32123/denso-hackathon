import argparse


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description="Local KnowFlow pilot API and citation viewer")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    # Local-only by default; no public exposure of the pilot caption corpus.
    uvicorn.run("retrieval.api.app:create_app", factory=True, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
