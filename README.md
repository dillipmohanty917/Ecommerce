# MedleyMed B2B2

Prerequisites

```
Python 3.8.10
```

## Installation

Install dependencies:

```
python3 -m venv b2b2-venv
source b2b2-venv/bin/activate
pip install -r requirements.txt
```

## To prepare local database:

```
sudo -u postgres psql
\l
CREATE DATABASE b2b2new;
GRANT ALL PRIVILEGES ON DATABASE b2b2new TO mphsbizto;
ALTER DATABASE b2b2new OWNER TO mphsbizto;
ALTER user mphsbizto with password 'password123';
\l
\q


python3 manage.py makemigrations
or 
python3 manage.py makemigrations Usermanagement Productmanagement Paymentmanagement Ordermanagement Activitylog
...
python3 manage.py migrate
```

## Frequent use commands:

```
pip3 freeze > requirements.txt

sudo lsof -t -i tcp:8000 | xargs kill -9

find . -name "*.pyc" -exec rm -f {} +
find . -name "__pycache__" -exec rm -r {} \;
```