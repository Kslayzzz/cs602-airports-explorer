# Global Airports Data Explorer

**Live app:** https://ziming-airports.streamlit.app/

57,421 airport records joined to a 246-row ISO country reference, six linked views, and a sidebar that reports what was excluded and why.

## The bug that made this project worth doing

pandas reads the literal string `NA` as a missing value. In this dataset `NA` is real data: it is North America, and it is Namibia.

A plain `read_csv` silently turned every one of those into NaN. Nothing failed. No error was raised. **28,443 North American airports and all 246 Namibian records disappeared from every filter and group-by downstream.**

I caught it by checking the row count against what it should have been.

Fix: `keep_default_na=False` on load.

## Two impossible records

One row sat at the North Pole. One claimed 29,977 ft of elevation. One was a personal-loan advertisement filed as a large airport.

They are excluded by physical rule, not by hardcoded ID:

- latitude beyond the pole
- elevation above 22,000 ft

A rule survives a data refresh. An ID list does not.

The latitude test is one-sided on purpose. The South Pole has a real runway, NZSP at Amundsen-Scott Station, so a southern outlier is not automatically wrong.

## Design write-up

**[DESIGN.md](DESIGN.md)** — the questions the app answers, why each chart type was chosen over the alternatives, and what I expected to find before building it.

## Stack

Python, pandas, Streamlit, Plotly, PyDeck

Built for CS602 at Bentley University, Summer 2026.
