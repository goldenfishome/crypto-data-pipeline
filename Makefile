.PHONY: up down logs shell \
        ingest-coingecko ingest-fear-greed \
        dbt-run dbt-test dbt-compile \
        test lint fmt \
        metabase \
        tf-init tf-plan tf-apply tf-destroy

# ── Local Airflow ─────────────────────────────────────────────────────────────
up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

shell:
	docker-compose exec airflow-scheduler bash

# ── Ingestion (local) ─────────────────────────────────────────────────────────
ingest-coingecko:
	python ingestion/coingecko.py --date $(shell date +%Y-%m-%d)

ingest-fear-greed:
	python ingestion/fear_greed.py --date $(shell date +%Y-%m-%d)

# ── dbt ───────────────────────────────────────────────────────────────────────
dbt-run:
	cd dbt && dbt run

dbt-test:
	cd dbt && dbt test

dbt-compile:
	cd dbt && dbt compile

# ── Tests & linting ───────────────────────────────────────────────────────────
test:
	pytest tests/ -v

lint:
	flake8 ingestion/ dags/ --max-line-length=100
	sqlfluff lint dbt/models/ --dialect redshift

fmt:
	black ingestion/ dags/

# ── Metabase ──────────────────────────────────────────────────────────────
metabase:
	open http://localhost:3000

# ── Terraform ─────────────────────────────────────────────────────────────────
tf-init:
	cd terraform && terraform init

tf-plan:
	cd terraform && terraform plan

tf-apply:
	cd terraform && terraform apply

tf-destroy:
	cd terraform && terraform destroy
