# CS 602 Final Project — Part 1: Design

**Name:** Ziming Shen
**Data set:** Airports around the World (`airport-codes.csv`, joined to `wikipedia-iso-country-codes.csv`)

## What I want to show and tell

The airport file lists 57,421 airfields, but almost nobody thinks of an airport as
anything other than a terminal with gates. Most of the rows here are small strips,
helipads and seaplane bases. The story I want to tell is that the world's air
network is mostly made of very small places, that where those places sit says a lot
about the country they are in, and that a few of them are in genuinely strange
locations — below sea level, or above 10,000 feet.

To tell it I have to fix something first. The dataset uses `NA` as the code for
North America, and also as the country code for Namibia. Pandas reads the string
`NA` as a missing value unless it is told not to, so the ordinary way of loading
this file quietly deletes 28,443 North American airports and all 246 Namibian ones,
and it blanks Namibia out of the country table as well, so the join cannot put it
back. Half the dataset disappears without any error message. Everything below
depends on loading it correctly.

## Three questions the user can ask

Each question takes a parameter that comes from a control in the sidebar.

**1. Which countries have the most airports, when I only count `<airport type>`?**
The answer changes shape completely depending on the type. Counting everything, the
United States is far ahead because its registry includes private strips and hospital
helipads that most countries never record. Counting only large airports, the gap
narrows and the ranking looks much more like what people expect.
*Parameter:* the airport types, from a multi-select.

**2. How high do airports sit in `<continent>`, and which ones are the outliers?**
Elevation is where the geography shows through. Europe's distribution is squat and
close to sea level; Asia and South America have long tails from the Himalayas and
the Andes.
*Parameters:* the continent from a dropdown, and an elevation band from a range
slider.

**3. Where are the airports in `<country>`, and which is the highest?**
This is the map question. Once a country is chosen, its airfields are plotted and
the highest and lowest are reported by name.
*Parameters:* the country from a dropdown, plus the type multi-select from
question 1.

## Streamlit controls I will use

| Control | What the user picks | Where it is used |
|---|---|---|
| `st.sidebar.radio` | which of the three views to look at | navigation |
| `st.sidebar.selectbox` | a country, and a continent | questions 2 and 3 |
| `st.sidebar.multiselect` | one or more airport types | questions 1 and 3 |
| `st.sidebar.slider` | elevation band, and histogram bar count | question 2 |

Page design: a wide layout, a custom page title and plane icon, every control kept
in the sidebar so the main panel is only results, and a small stylesheet that puts
the headings and metric boxes in a consistent blue.

## How the results will be presented

**Horizontal bar chart** — countries ranked by airport count, with the exact figure
printed at the end of each bar so the reader does not have to measure against the
axis. Horizontal rather than vertical because country names are long.

**Histogram** — the spread of elevations, with a dashed line marking the mean so the
long right tail is obvious.

**Stacked bar chart** — the mix of airport types on each continent, one colour per
type with a legend. The pivot table behind it is available in an expander, because
some readers want the numbers rather than the picture.

**PyDeck map** — every airport in the chosen selection as a dot, coloured by the
same type colours used in the stacked bar so the two views agree. Hovering a dot
shows the airport's name, its town, its type and its elevation. A plain `st.map`
would put down featureless dots; the point of using PyDeck is the colour coding and
the hover text.

**Tables and metric boxes** — the ten highest airports in the chosen country, the
airfields below sea level or above 10,000 feet, and metric boxes for the headline
counts.

## What I expect to find

That small airports and heliports dominate every continent; that the United States'
lead shrinks sharply once only large airports are counted; that European elevations
cluster near sea level while Asian and South American ones spread much wider; and
that the below-sea-level airfields cluster in a few specific places, such as the
Caspian Depression, rather than being scattered errors.
