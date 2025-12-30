# Lawyer Lead-Gen Services Scraper

This project scrapes an article page (e.g. a Clio blog post) and exports the lead generation services and their review content into a CSV file.

## Requirements

- Python 3.9+

## Install dependencies

```bash
python3 -m pip install -r requirements.txt
```

## Run

Pass the article URL as the only required argument:

```bash
python3 main.py "<ARTICLE_URL>"
```

## Output

- By default, the script writes a CSV into the `results/` folder.
- The filename is generated from the URL slug + a timestamp.

## Custom output path

To specify an explicit CSV output path:

```bash
python3 main.py "<ARTICLE_URL>" -o results/output.csv
```

## Notes

- If you are publishing this to GitHub, it’s typical to exclude `results/` from version control (add it to `.gitignore`).
