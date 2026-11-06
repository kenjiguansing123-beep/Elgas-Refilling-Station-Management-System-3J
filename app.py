"""ELGAS Refueling Management System - run with:  python app.py"""
from elgas import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
