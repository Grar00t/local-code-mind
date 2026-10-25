# Sovereign v1.1.0

The local analyzer uses the Python standard library only. Scans and HTML/JSON export do not contact remote services. Python 3.10+ is required; Git is optional for metadata.

## Run without installation

```powershell
python -S src/main.py . --dead-code
python -S src/main.py . --dead-code --json
python -I -S -m unittest discover -s tests -v
python -S tools/build_zipapp.py
python -I -S dist/local-code-mind.pyz . --dead-code --html reports/audit.html
```
