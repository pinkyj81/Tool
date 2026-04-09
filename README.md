# ToolReplaceWeb

Standalone Flask app for managing `dbo.ToolReplace` in `yujincast`.

## 1) Setup

```powershell
cd ToolReplaceWeb
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2) Environment Variables (optional)

```powershell
$env:TOOLREPLACE_DB_SERVER="ms1901.gabiadb.com"
$env:TOOLREPLACE_DB_DATABASE="yujincast"
$env:TOOLREPLACE_DB_USERNAME="your_user"
$env:TOOLREPLACE_DB_PASSWORD="your_password"
$env:TOOLREPLACE_SECRET_KEY="change-me"
```

If not provided, defaults in `app.py` are used.

## 3) Run

```powershell
python app.py
```

Open: http://127.0.0.1:5050
