"""
System smoke test — verifies the environment is set up correctly.

    python test_setup.py
"""

import sys


def check(label, fn):
    try:
        fn()
        print(f"  OK  {label}")
        return True
    except Exception as e:
        print(f"  FAIL {label}: {e}")
        return False


def main():
    print("\nEventView — system check\n")
    results = []

    results.append(check("Python >= 3.11", lambda: assert_python()))
    results.append(check("requests", lambda: __import__("requests")))
    results.append(check("beautifulsoup4", lambda: __import__("bs4")))
    results.append(check("lxml", lambda: __import__("lxml")))
    results.append(check("sqlalchemy", lambda: __import__("sqlalchemy")))
    results.append(check("fastapi", lambda: __import__("fastapi")))
    results.append(check("uvicorn", lambda: __import__("uvicorn")))
    results.append(check("apscheduler", lambda: __import__("apscheduler")))
    results.append(check("dateutil", lambda: __import__("dateutil")))
    results.append(check("Database init", check_db))
    results.append(check("Network (visitregiobarneveld.nl)", check_network))

    print()
    passed = sum(results)
    print(f"{passed}/{len(results)} checks passed.")
    if passed < len(results):
        sys.exit(1)


def assert_python():
    assert sys.version_info >= (3, 11), f"Need Python 3.11+, got {sys.version}"


def check_db():
    from models import init_db, SessionLocal, Event
    init_db()
    db = SessionLocal()
    db.query(Event).count()
    db.close()


def check_network():
    import requests
    r = requests.get("https://visitregiobarneveld.nl/agenda/", timeout=10)
    r.raise_for_status()


if __name__ == "__main__":
    main()
