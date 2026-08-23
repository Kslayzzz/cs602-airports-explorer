# Global Airports Data Explorer

Live app: https://ziming-airports.streamlit.app/

## The problem

Open airport data is messy in ways that don't announce themselves. Country codes
live in one file, airport records in another, and the join looks fine even when
it isn't. Anyone building on top of it inherits the errors silently.

This app loads 57,421 airport records, joins them to a 246-row ISO country
reference, and gives you six linked views. It also shows you what it threw out
and why.

## What I found

**A silent data loss of 28,443 records.**

pandas reads the literal string `NA` as a missing value. In this dataset `NA` is
real data: it's North America, and it's Naturned every
one of those into NaN. Nothing failed. No error was raised. North America simply
disappeared from every filter and group-by

I caught it by checking the row count agaien. 28,443
North American airports and all 246 Namibian records were gone.

Fix: `keep_default_na=False` on load, so `NA` stays a string.

## Two impossible records

One airport sat at the North Pole. Another claimed 29,977 ft of elevation. A
third was a personal-loan advertisement fi

I excluded them by physical rule, not by h

- latitude beyond the pole
- elevation above 22,000 ft

The rule survives a data refresh. A hardcoded ID list doesn't.

The latitude test is one-sided on purpose. The South Pole has a real runway —
NZSP, Amundsen-Scott Station — so a southecally wrong.

## The audit trail

The source CSV is never modified. All filtnd the
sidebar reports exactly what was excluded and under which rule. If you disagree
with a filter, you can see it and change i

## Stack

Python, pandas, Streamlit, Plotly, PyDeck

## Context

Built for CS602 at Bentley University, Sum
