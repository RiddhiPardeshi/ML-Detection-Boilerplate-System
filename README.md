# Generic ML Boilerplate

Reusable FastAPI backend boilerplate for tabular machine-learning applications. The application infrastructure stays stable across use cases such as classification, detection, emotion recognition, food classification, and text classification; the ML-specific components can be replaced or extended for each project.

The backend currently provides configuration, database models, authentication foundations, RBAC foundations, admin user management, reusable tabular ML components, model persistence, inference, and prediction persistence. The frontend directory is reserved for a future React application.

## Architecture

The application request flow is:

```text
FastAPI application
        |
       API
        |
    Services
        |
     ML Layer
        |
   Persistence
        |
   PostgreSQL
```

The ML workflow is intentionally separated into reusable stages:

```text
Data Loading
      |
Preprocessing
      |
Train/Test Split
      |
   Training
      |
  Evaluation
      |
Model Persistence
      |
   Inference
```

The API handles HTTP concerns, services handle business operations, the ML layer handles model workflows, persistence stores model artifacts and application records, and PostgreSQL is the target application database.

## Project Structure

```text
generic-ml-boilerplate/
├── backend/
│   └── app/
│       ├── api/
│       ├── config/
│       ├── core/
│       ├── database/
│       ├── ml/
│       │   ├── data/
│       │   ├── evaluation/
│       │   ├── inference/
│       │   ├── models/
│       │   ├── preprocessing/
│       │   └── training/
│       ├── models/
│       ├── schemas/
│       └── services/
├── frontend/
├── ml/
├── tests/
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

### Application Packages

- `backend/app/api/`: FastAPI route definitions and centralized router registration.
- `backend/app/config/`: Environment-backed application settings.
- `backend/app/core/`: Cross-cutting security and authorization helpers, including password hashing and RBAC dependencies.
- `backend/app/database/`: SQLAlchemy `Base`, engine, session factory, and FastAPI database-session dependency.
- `backend/app/models/`: SQLAlchemy application models, including `User` and `Prediction`.
- `backend/app/schemas/`: Pydantic request and response schemas kept separate from SQLAlchemy models.
- `backend/app/services/`: Authentication, admin user-management, and prediction-persistence business logic.

### ML Packages

- `backend/app/ml/data/`: Generic CSV loading and train/test splitting.
- `backend/app/ml/preprocessing/`: Reusable numeric and categorical preprocessing with `ColumnTransformer`.
- `backend/app/ml/models/`: The `TabularModel` interface and joblib model-artifact persistence.
- `backend/app/ml/training/`: Training orchestration using a `TabularModel` and optional `TabularPreprocessor`.
- `backend/app/ml/evaluation/`: Classification metrics and confusion-matrix evaluation.
- `backend/app/ml/inference/`: Prediction and optional probability-prediction services.

The root-level `ml/` directory contains the original placeholder ML structure from project initialization. The implemented FastAPI application ML layer is under `backend/app/ml/`.

## Configuration

Copy `.env.example` to an environment-specific configuration source and replace placeholders with local values. `.env.example` contains examples and placeholders only; it contains no real credentials or secrets.

Supported environment variables:

| Variable | Purpose | Example/default |
| --- | --- | --- |
| `APP_NAME` | FastAPI application title | `Generic ML Boilerplate` |
| `APP_ENV` | Application environment name | `development` |
| `DEBUG` | Enables FastAPI debug mode when truthy | `false` |
| `DATABASE_URL` | PostgreSQL SQLAlchemy connection URL | `postgresql://<user>:<password>@<host>:5432/<database>` |
| `ML_MODEL_PATH` | Filesystem path to the joblib model artifact | `artifacts/model.joblib` |
| `ML_MODEL_IDENTIFIER` | Identifier stored with prediction records | `generic-ml-model` |
| `ML_MODEL_VERSION` | Version stored with prediction records | `unknown` |

All environment reads are centralized in `backend/app/config/settings.py`. Model paths are normalized as `Path` values. The database URL is required for real PostgreSQL use; the development fallback does not contain credentials.

## Installation

From the repository root:

```powershell
python -m pip install -r requirements.txt
```

This installs FastAPI, SQLAlchemy, the PostgreSQL DBAPI driver, password hashing support, pandas, scikit-learn, joblib, pytest, and the `httpx2` package required by the installed Starlette test client.

## Running the Application

The FastAPI application object is `app` in `backend/app/main.py`. With Uvicorn available in the environment, start it from the repository root with:

```powershell
python -m uvicorn backend.app.main:app --reload
```

The command does not create database tables. Real database-backed operation requires a valid `DATABASE_URL` and an available PostgreSQL server. A trained model artifact must also exist at `ML_MODEL_PATH` before calling the prediction endpoint.

## Testing

Run the test suite from the repository root:

```powershell
pytest tests -q
```

Current validation result:

```text
33 passed
0 failed
0 errors
0 skipped
```

The tests use small in-memory data, temporary files, fakes, and metadata inspection. They do not require a live PostgreSQL server or create real database tables.

## API Endpoints

These are the routes currently registered by the application:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Returns `{"status": "ok"}`. |
| `POST` | `/auth/register` | Registers a user from `username`, `email`, and `password`; stores only a password hash. Duplicate username/email returns `409`. |
| `POST` | `/auth/login` | Verifies an email/password pair and returns the safe user response; invalid credentials return `401`. |
| `GET` | `/admin/users` | Lists all users; admin-only. |
| `GET` | `/admin/users/{user_id}` | Gets one user; admin-only. |
| `PATCH` | `/admin/users/{user_id}/activate` | Activates a user; admin-only. |
| `PATCH` | `/admin/users/{user_id}/deactivate` | Deactivates a user; admin-only. |
| `PATCH` | `/admin/users/{user_id}/role` | Changes a user role between `USER` and `ADMIN`; admin-only. |
| `POST` | `/ml/predict` | Loads the configured artifact, predicts from a generic feature mapping, optionally returns probabilities, and persists the output. |

Admin routes use the existing `require_admin` dependency. The current authentication foundation verifies credentials but does not yet issue JWTs or implement OAuth/social login. The authorization helper expects an authenticated `User` to be placed on the request state by an authentication integration.

## ML Extension Guide

A future application can keep the infrastructure and replace only its ML-specific implementation:

1. Load a dataset with `backend.app.ml.data.load_csv` or another application-specific loader.
2. Define numeric and categorical feature handling with `TabularPreprocessor`, or extend the preprocessing layer for the dataset.
3. Split features and labels with `split_dataset` before fitting transformations or models.
4. Implement a concrete class that satisfies the `TabularModel` `fit(X, y)` and `predict(X)` interface. Add `predict_proba(X)` when supported.
5. Use `train_model` with training data and an optional preprocessor.
6. Evaluate held-out data with `evaluate_classification`.
7. Save the trained model and fitted preprocessor together with `save_model`.
8. Load the artifact with `load_model` and use the inference `predict` or `predict_proba` service for new input.
9. Expose application-specific prediction input through the existing `/ml/predict` API pattern.

No concrete algorithm is included in the generic infrastructure. The future project chooses its estimator, labels, feature definitions, dataset, and model-selection strategy.

## Separation of Responsibilities

```text
Loader         -> loads data only
Preprocessor   -> transforms features
Splitter       -> creates train/test sets
Model          -> provides fit/predict interface
Training       -> orchestrates fitting on training data
Evaluation     -> calculates classification metrics on test data
Persistence    -> saves and loads model artifacts
Inference      -> transforms new input and performs prediction
API            -> handles HTTP requests and response mapping
Database       -> persists application data and prediction records
```

Successful prediction outputs are persisted through the prediction service. The raw feature input is used for inference but is not stored by default. A prediction can optionally be associated with the authenticated requesting `User`.

## Authentication, RBAC, and Admin

Authentication foundations include password hashing and verification, user registration, and login. Plain-text passwords are never stored; the `User` model stores only `password_hash`.

The RBAC foundation defines two roles: `USER` and `ADMIN`. `require_authenticated_user` and `require_admin` are reusable authorization dependencies. Admin user-management routes require the admin dependency and support listing users, retrieving a user, activation/deactivation, and changing roles. Roles and permissions beyond these foundations are not implemented.

## PostgreSQL and Database Behavior

PostgreSQL is the target database. Configure its SQLAlchemy URL with `DATABASE_URL`. The application provides a reusable engine, session factory, declarative `Base`, and `get_db` dependency.

The repository intentionally does not include database migrations or automatic table creation. No production code calls `Base.metadata.create_all()`. A PostgreSQL server and appropriate database setup are required for real database-backed use.

## Reusability

Another tabular ML project can reuse the authentication, user management, admin, database, configuration, API, and persistence infrastructure while replacing or extending the ML packages under `backend/app/ml/`. The generic contracts allow the project-specific dataset, preprocessing choices, labels, concrete model, training process, evaluation details, and inference input schema to evolve independently.

## Known Limitations

- PostgreSQL must be configured and available for real database usage.
- A trained joblib model artifact must exist before real inference.
- The boilerplate does not contain a concrete ML algorithm.
- Dataset and model selection are intentionally application-specific.
- JWT, OAuth/social login, and authentication middleware are not implemented.
- Database migrations and automatic table creation are not included.
- The frontend directory is currently a placeholder.
