"""
Name:       Ziming Shen
CS602:      Summer 2026, Monday 6:00-9:30 pm, Smith 203 (Prof. Anqi Xu)
Data:       Airports around the World (airport-codes.csv + wikipedia-iso-country-codes.csv)
URL:        https://ziming-airports.streamlit.app/

Description:

This program is an interactive explorer for the OurAirports dataset, which lists
57,421 airfields worldwide. Two of those rows describe places that cannot exist
and are set aside on load, leaving 57,419; see drop_impossible_records(). It answers three questions the user controls from the sidebar: which
countries have the most airports of a chosen type, how airport elevation is
distributed inside a chosen continent, and where a chosen country's airports
actually sit on the map. The app joins the airport table to the Wikipedia ISO
country-code table so results are labelled with real country names instead of
two-letter codes, and it reports the highest and lowest airfields in whatever
slice the user has selected. Views are a bar chart of leading countries, a
histogram of elevations with mean, median and 90th-percentile markers, a stacked
bar of type composition by continent, a pivot table behind that chart, a pie
chart of one country's airfield mix with its largest slice pulled out, an
interactive Plotly scatter of elevation against latitude, and a PyDeck map whose
dots are coloured by airport type and show the airport's name, municipality and
elevation on hover.

Two packages we did not cover in class are used here, each documented in full at
the point where it is used:
  - plotly    - the interactive scatter plot, see draw_height_against_latitude()
  - pycountry - naming the countries the ISO spreadsheet missed, see
                name_the_leftovers()

References consulted beyond the class examples:
  - pandas, "IO tools: na_values / keep_default_na"
    https://pandas.pydata.org/docs/user_guide/io.html#na-values
    This is where the behaviour behind the [DA1] fix below is documented.
  - PyDeck ScatterplotLayer and tooltip options
    https://deckgl.readthedocs.io/en/latest/layer.html
  - Streamlit API reference, for st.tabs, st.plotly_chart and st.cache_data
    https://docs.streamlit.io/develop/api-reference
  - Plotly Express scatter, for render_mode and hover_data
    https://plotly.com/python-api-reference/generated/plotly.express.scatter.html
  - pycountry, for the ISO 3166-1 lookup
    https://pypi.org/project/pycountry/
  - Data source background: https://datahub.io/core/airport-codes
    (the CSV files themselves are the ones supplied with the assignment)
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import pycountry
import pydeck as pdk
import streamlit as st

AIRPORTS_FILE = "airport-codes.csv"
COUNTRIES_FILE = "wikipedia-iso-country-codes.csv"

# One palette drives the whole application, so the charts, the map dots and the
# page furniture all agree with each other instead of each picking its own blue.
INK = "#10263a"
PRIMARY = "#1f6f9e"
PRIMARY_SOFT = "#6aa9cd"
PALE = "#b9d9ea"
ACCENT = "#e8845f"
GREEN = "#5f9e8f"
MUTED = "#5b7186"
GRIDLINE = "#e6eef4"

# [PY5] A dictionary whose keys, values and items are all read below: the keys become
# the continent filter, the values label the charts, and .items() builds the legend.
CONTINENT_NAMES = {
    "AF": "Africa",
    "AN": "Antarctica",
    "AS": "Asia",
    "EU": "Europe",
    "NA": "North America",
    "OC": "Oceania",
    "SA": "South America",
}

# XK is the one code pycountry cannot resolve, and that is correct behaviour rather
# than a gap: XK is a "user-assigned" code that aviation and banking systems adopted
# for Kosovo, but it was never admitted to ISO 3166-1 because Kosovo's statehood is
# not universally recognised. A standards library should not invent it, so the one
# name it cannot supply is the one name this program still has to state itself.
USER_ASSIGNED_CODES = {
    "XK": "Kosovo",
}

# The three runway sizes get a light-to-dark blue ramp so the ordering is visible
# at a glance; the categories that are not a size get their own distinct hue.
TYPE_COLORS = {
    "large_airport": "#10263a",
    "medium_airport": PRIMARY,
    "small_airport": PRIMARY_SOFT,
    "heliport": ACCENT,
    "seaplane_base": GREEN,
    "closed": "#b6c2cc",
    "balloonport": "#e9c46a",
}

# PyDeck needs RGB lists rather than hex strings for its dot colours.
TYPE_RGB = {
    "large_airport": [16, 38, 58],
    "medium_airport": [31, 111, 158],
    "small_airport": [106, 169, 205],
    "heliport": [232, 132, 95],
    "seaplane_base": [95, 158, 143],
    "closed": [182, 194, 204],
    "balloonport": [233, 196, 106],
}


def style_charts():
    """Apply one matplotlib theme to every figure the app draws.

    The defaults render at 100 dpi inside a box of four black spines, which looks
    coarse on a high-resolution screen. Raising the resolution, softening the
    gridlines and dropping the spines is what makes the charts look finished.
    """
    plt.rcParams.update({
        "figure.dpi": 200,
        "savefig.dpi": 200,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "font.size": 9,
        "text.color": INK,
        "axes.titlesize": 12.5,
        "axes.titleweight": "bold",
        "axes.titlecolor": INK,
        "axes.titlepad": 16,
        "axes.labelsize": 9.5,
        "axes.labelcolor": MUTED,
        "axes.edgecolor": GRIDLINE,
        "axes.linewidth": 0.9,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRIDLINE,
        "grid.linewidth": 0.9,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelsize": 8.5,
        "ytick.labelsize": 8.5,
        "legend.frameon": False,
        "legend.fontsize": 8.5,
    })


def tidy_axes(ax, keep_left=True, keep_bottom=True):
    """Strip the chart junk: no top or right spine, and only the gridlines that help."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(keep_left)
    ax.spines["bottom"].set_visible(keep_bottom)
    ax.tick_params(length=0)


def drop_impossible_records(airports):
    """[DA1] Remove records that cannot describe a real airfield.

    [PY2] Returns two values: the surviving rows and how many were dropped, so the
    page can tell the reader what was removed instead of quietly shrinking.

    OurAirports is crowd-sourced, and this snapshot carries two rows that cannot
    be real. XXZ, named "Modi", sits at 89.9998 N / 179.9999 E, which is the
    North Pole, while its municipality column says California and its elevation
    says 29,977 ft - higher than the summit of Everest at 29,032 ft. SA-0009 is
    not an airport at all but an advertisement for personal loans, filed as a
    large_airport at 90 N / 90 E.

    The temptation is to delete those two idents by name. That would be choosing
    the data I like rather than cleaning it, and it would fix nothing if a third
    bad row appeared. So this applies two physical tests instead, and the two
    known rows simply happen to fail them.

    The northern test is deliberately one-sided. The geographic North Pole is
    floating sea ice with no airfield on it, but the South Pole sits on the
    Antarctic ice sheet and genuinely has one - NZSP, the runway at Amundsen-Scott
    station, at latitude -90. A symmetric test would throw away a real airport.

    The data files themselves are left exactly as supplied; this filtering happens
    only in memory, so the CSV submitted with this project still matches the one
    handed out.
    """
    # No airfield exists at the North Pole. The South Pole is deliberately spared.
    at_north_pole = airports["lat"] > 89.9
    # Siachen Glacier AFS at 22,000 ft is the highest helipad in the world, so
    # anything above that is a transcription error rather than an airfield.
    above_the_highest_helipad = airports["elevation_ft"] > 22000

    impossible = at_north_pole | above_the_highest_helipad
    return airports[~impossible], int(impossible.sum())


def name_the_leftovers(airports):
    """Name every country the Wikipedia ISO table failed to cover, using pycountry.

    MODULE NOT TAUGHT IN CLASS - pycountry (https://pypi.org/project/pycountry/)

    The country names in this app come from wikipedia-iso-country-codes.csv, but
    that file is a snapshot and it predates several codes the airport data uses:
    BQ, CW, SS and SX all arrived after it was written, so 58 airports came out of
    the join with no country at all. The obvious fix is to type those four names
    into a dictionary, which is what this program did at first. The problem with
    that fix is that it only repairs the gaps I happened to notice; the next time
    a country code is added, the join goes quiet again.

    pycountry carries the maintained ISO 3166-1 list as a package, so instead of
    naming specific countries this function asks the standard for whatever the
    spreadsheet is missing. It repairs codes I never looked for.

    [PY5] The lookup reads a dictionary's keys and values for the one code that
    genuinely is not in the standard.
    """
    unnamed = airports["country_name"].isna() | (airports["country_name"] == "")
    for code in airports.loc[unnamed, "iso_country"].unique():
        if code == "":
            continue
        standard_entry = pycountry.countries.get(alpha_2=code)
        if standard_entry is not None:
            name = standard_entry.name
        elif code in USER_ASSIGNED_CODES:
            name = USER_ASSIGNED_CODES[code]
        else:
            continue
        airports.loc[airports["iso_country"] == code, "country_name"] = name
    return airports


@st.cache_data
def load_data():
    """Read both CSV files, clean them, and join them into one DataFrame."""

    # *** The thing I am most proud of in this program ***
    # [DA1] Clean the data.
    # pandas treats the literal string "NA" as a missing value by default. In this
    # dataset "NA" is not missing at all: in the continent column it means North
    # America, and in the country column it means Namibia. Reading the files the
    # ordinary way silently erases 28,443 North American airports and all 246
    # Namibian ones, and it also blanks Namibia's row in the country table so the
    # join cannot match it back. Turning the default off and treating only an empty
    # string as missing is what keeps half the dataset alive.
    no_na_tricks = dict(keep_default_na=False, na_values=[""])
    airports = pd.read_csv(AIRPORTS_FILE, **no_na_tricks)
    countries = pd.read_csv(COUNTRIES_FILE, **no_na_tricks)

    # [DA7] Select and rename the columns worth keeping, and drop the rest.
    countries = countries[["Alpha-2 code", "English short name lower case"]]
    countries.columns = ["iso_country", "country_name"]

    airports = airports.merge(countries, on="iso_country", how="left")
    airports = name_the_leftovers(airports)

    # [DA9] Create new columns. The coordinates arrive as one "lon, lat" string,
    # so it has to be split before any map can use it.
    lon_lat = airports["coordinates"].str.split(",", expand=True)
    airports["lon"] = pd.to_numeric(lon_lat[0], errors="coerce")
    airports["lat"] = pd.to_numeric(lon_lat[1], errors="coerce")

    airports["elevation_ft"] = pd.to_numeric(airports["elevation_ft"], errors="coerce")
    airports["continent_name"] = airports["continent"].map(CONTINENT_NAMES)

    # A readable label for the airport type, used on every axis and legend.
    airports["type_label"] = airports["type"].str.replace("_", " ").str.title()

    # Rows with no usable position cannot be mapped or measured.
    airports = airports.dropna(subset=["lat", "lon"])

    # [PY2] The second cleaning pass hands back both the data and a count.
    airports, dropped = drop_impossible_records(airports)
    return airports, dropped


# [PY3] Returns a value and is called from five different places: the country page,
# the type-mix pie, the comparison chart, the elevation page and the extremes table
# all go through this one function.
# [DA4] Filter by one condition and [DA5] filter by several conditions with AND.
def filter_airports(df, continent=None, country=None, types=None, elevation_range=None):
    """Return the subset of df that matches whichever filters were supplied."""
    result = df
    if continent:
        result = result[result["continent"] == continent]
    if country:
        result = result[result["country_name"] == country]
    if types:
        result = result[result["type"].isin(types)]
    if elevation_range:
        low, high = elevation_range
        result = result[(result["elevation_ft"] >= low) & (result["elevation_ft"] <= high)]
    return result


# [DA2] Sort in descending order. [DA3] Take the largest values of a column.
def top_countries(df, count=10):
    """Return the countries holding the most airports, largest first."""
    tally = df["country_name"].value_counts().head(count)
    return tally.sort_values(ascending=True)


# [PY2] Returns more than one value.
def elevation_extremes(df):
    """Return the highest and the lowest airport in df, plus the average elevation."""
    measured = df.dropna(subset=["elevation_ft"])
    if measured.empty:
        return None, None, 0.0
    highest = measured.loc[measured["elevation_ft"].idxmax()]
    lowest = measured.loc[measured["elevation_ft"].idxmin()]
    return highest, lowest, measured["elevation_ft"].mean()


# [PY1] Three parameters, the last with a default value, and it is genuinely called
# both ways: the Overview page calls draw_top_countries(data, 10) and lets highlight
# default to None, while the country page passes highlight=chosen_country so that
# one bar comes out in the accent colour.
def draw_top_countries(df, count, highlight=None):
    """[VIZ1] Horizontal bar chart of the countries with the most airports."""
    tally = top_countries(df, count)
    fig, ax = plt.subplots(figsize=(8, 0.34 * len(tally) + 1.4))

    # One country can be picked out in the accent colour so the reader's eye lands
    # on the country they chose rather than having to hunt for its label.
    bar_colors = [ACCENT if name == highlight else PRIMARY for name in tally.index]
    ax.barh(tally.index, tally.values, color=bar_colors, height=0.72)

    ax.set_title(f"Countries with the most airports (top {count})", loc="left")
    ax.set_xlabel("Number of airports")
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    tidy_axes(ax, keep_left=False, keep_bottom=False)
    ax.set_xlim(0, tally.max() * 1.13)

    # The exact figure at the end of each bar, so nobody has to read against the axis.
    for name, value in tally.items():
        ax.text(value + tally.max() * 0.015, name, f"{value:,}",
                va="center", fontsize=8.5, color=MUTED)

    fig.tight_layout()
    return fig


def draw_elevation_histogram(df, bins):
    """[VIZ2] Histogram showing how airport elevations are spread out."""
    measured = df.dropna(subset=["elevation_ft"])
    heights = measured["elevation_ft"].to_numpy()

    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    ax.hist(heights, bins=bins, color=PALE, edgecolor="white", linewidth=0.6)

    # NumPy does the summary statistics. The mean alone is misleading here because
    # a few very high airfields drag it upward, so the median and the 90th
    # percentile are drawn beside it to show how skewed the distribution really is.
    average = np.mean(heights)
    median = np.median(heights)
    ninetieth = np.percentile(heights, 90)
    for value, colour, style, label in [
        (median, PRIMARY, "-", f"Median  {median:,.0f} ft"),
        (average, ACCENT, "--", f"Mean  {average:,.0f} ft"),
        (ninetieth, GREEN, ":", f"90th pct  {ninetieth:,.0f} ft"),
    ]:
        ax.axvline(value, color=colour, linestyle=style, linewidth=1.8, label=label)

    ax.set_title("How high the airfields sit", loc="left")
    ax.set_xlabel("Elevation (feet)")
    ax.set_ylabel("Number of airports")
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right")
    tidy_axes(ax, keep_left=False, keep_bottom=True)
    fig.tight_layout()
    return fig


def draw_type_mix(pivot):
    """[VIZ3] Stacked bar chart of how airport types are mixed on each continent."""
    fig, ax = plt.subplots(figsize=(9, 4.4))
    bottom = [0] * len(pivot.index)
    # [PY4] A list comprehension builds the readable column labels.
    labels = [column.replace("_", " ").title() for column in pivot.columns]

    for column, label in zip(pivot.columns, labels):
        values = pivot[column].tolist()
        ax.bar(pivot.index, values, bottom=bottom, label=label, width=0.62,
               color=TYPE_COLORS.get(column, "#cccccc"))
        bottom = [carried + added for carried, added in zip(bottom, values)]

    ax.set_title("What kind of airfields each continent has", loc="left")
    ax.set_ylabel("Number of airports")
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    ax.legend(title="Type", bbox_to_anchor=(1.01, 1), loc="upper left")
    tidy_axes(ax, keep_left=False, keep_bottom=True)
    plt.setp(ax.get_xticklabels(), rotation=18, ha="right")
    fig.tight_layout()
    return fig


def draw_height_against_latitude(df, continent_name):
    """[VIZ6] Interactive scatter of elevation against latitude.

    MODULE NOT TAUGHT IN CLASS - Plotly (https://pypi.org/project/plotly/)

    Every other chart in this program is Matplotlib, which renders a picture. That
    is the right choice for the bar charts, where the reader only needs to compare
    a dozen values. It is the wrong choice here. This plot carries one dot per
    airport, and at that density a still image is a smear: the shape of the cloud
    is readable but no individual airport is.

    Plotly draws into the browser instead of into an image, so the same cloud
    becomes something you can interrogate. Hovering a dot names the airport,
    dragging a box zooms into a mountain range, and clicking a legend entry hides
    a whole category. WebGL rendering is what keeps that responsive with tens of
    thousands of points.
    """
    plot_frame = df.dropna(subset=["elevation_ft"])
    colour_map = {code.replace("_", " ").title(): shade
                  for code, shade in TYPE_COLORS.items()}

    figure = px.scatter(
        plot_frame,
        x="lat",
        y="elevation_ft",
        color="type_label",
        color_discrete_map=colour_map,
        hover_name="name",
        hover_data={"country_name": True, "municipality": True,
                    "elevation_ft": ":,.0f", "lat": ":.2f", "type_label": False},
        labels={"lat": "Latitude (degrees)", "elevation_ft": "Elevation (feet)",
                "type_label": "Type", "country_name": "Country",
                "municipality": "Town"},
        opacity=0.62,
        render_mode="webgl",
    )
    figure.update_traces(marker=dict(size=5, line=dict(width=0)))
    figure.update_layout(
        title=dict(text=f"Elevation against latitude in {continent_name}",
                   font=dict(size=17, color=INK), x=0, xanchor="left"),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color=MUTED, size=12),
        legend=dict(title="Type", orientation="v", x=1.01, y=1),
        margin=dict(l=10, r=10, t=60, b=10),
        height=470,
        hoverlabel=dict(bgcolor=INK, font=dict(color="white", size=12)),
    )
    # A line at sea level, so the airfields below it are unmistakable.
    figure.add_hline(y=0, line_width=1.2, line_dash="dot", line_color=MUTED)
    figure.update_xaxes(gridcolor=GRIDLINE, zeroline=False)
    figure.update_yaxes(gridcolor=GRIDLINE, zeroline=False)
    return figure


def draw_type_share(df, country_name):
    """[VIZ5] Pie chart of one country's airfield mix, with the biggest slice pulled out."""
    counts = df["type"].value_counts()
    # [PY4] A list comprehension turns the raw codes into readable legend labels.
    labels = [code.replace("_", " ").title() for code in counts.index]
    colours = [TYPE_COLORS.get(code, "#cccccc") for code in counts.index]

    # NumPy locates the largest slice so it can be offset from the centre. Pulling
    # one wedge out is what stops a pie chart from reading as an undifferentiated
    # circle, and it always points at the answer to "what is this country mostly?"
    shares = counts.to_numpy()
    offsets = np.zeros(len(shares))
    offsets[int(np.argmax(shares))] = 0.07

    fig, ax = plt.subplots(figsize=(6.6, 4.4))
    wedges, _, percent_labels = ax.pie(
        shares,
        explode=offsets,
        colors=colours,
        startangle=90,
        counterclock=False,
        # Only label a slice that is big enough to read; the rest stay in the legend.
        autopct=lambda share: f"{share:.1f}%" if share >= 4 else "",
        pctdistance=1.17,
        wedgeprops={"edgecolor": "white", "linewidth": 1.6},
    )
    for label in percent_labels:
        label.set_fontsize(9)
        label.set_color(MUTED)
        label.set_fontweight("bold")

    ax.set_title(f"What {country_name} is mostly made of", loc="left")
    ax.legend(wedges, labels, title="Type", loc="center left",
              bbox_to_anchor=(1.0, 0.5))
    ax.axis("equal")
    fig.tight_layout()
    return fig


def draw_map(df):
    """[MAP] [VIZ4] PyDeck scatter map, coloured by type, with details on hover."""
    plotted = df.copy()
    # [DA9] Perform a calculation on a column: PyDeck wants an RGB list per row.
    plotted["colour"] = plotted["type"].map(TYPE_RGB)
    plotted["colour"] = plotted["colour"].apply(
        lambda value: value if isinstance(value, list) else [150, 150, 150])
    plotted["elevation_text"] = plotted["elevation_ft"].apply(
        lambda feet: f"{feet:,.0f} ft" if pd.notna(feet) else "elevation unknown")
    plotted["municipality"] = plotted["municipality"].replace("", "Unknown town")

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=plotted[["lat", "lon", "name", "municipality", "country_name",
                      "type_label", "elevation_text", "colour"]],
        get_position=["lon", "lat"],
        get_fill_color="colour",
        get_radius=9000,
        radius_min_pixels=2.5,
        radius_max_pixels=13,
        stroked=True,
        get_line_color=[255, 255, 255],
        line_width_min_pixels=0.4,
        pickable=True,
        opacity=0.82,
    )
    view = pdk.ViewState(
        latitude=float(plotted["lat"].mean()),
        longitude=float(plotted["lon"].mean()),
        zoom=2.4 if len(plotted) > 3000 else 4.2,
        pitch=0,
    )
    tooltip = {
        "html": "<div style='font-size:12px;line-height:1.45'>"
                "<b style='font-size:13px'>{name}</b><br/>"
                "{municipality}, {country_name}<br/>"
                "<span style='opacity:.85'>{type_label} &middot; {elevation_text}</span>"
                "</div>",
        "style": {"backgroundColor": INK, "color": "white",
                  "borderRadius": "6px", "padding": "8px 10px"},
    }
    return pdk.Deck(layers=[layer], initial_view_state=view, tooltip=tooltip,
                    map_style="light")


def map_legend():
    """Draw a colour key for the map, since PyDeck will not make one itself."""
    swatches = "".join(
        f"<span class='key'><i style='background:{TYPE_COLORS[code]}'></i>"
        f"{code.replace('_', ' ').title()}</span>"
        for code in TYPE_COLORS
    )
    st.markdown(f"<div class='legend'>{swatches}</div>", unsafe_allow_html=True)


def page_overview(data):
    """Opening page: headline numbers, leading countries, and the type mix."""
    st.markdown(
        "<p class='lede'>Almost nobody pictures an airport as anything but a "
        "terminal with gates. Most of the 57,421 airfields in this dataset are "
        "nothing of the sort — they are farm strips, hospital helipads and lakes "
        "where floatplanes land. This page sets the scale before the other two "
        "pages narrow it down.</p>",
        unsafe_allow_html=True,
    )

    total = len(data)
    countries_covered = data["country_name"].nunique()
    with_iata = data["iata_code"].replace("", pd.NA).notna().sum()
    large = (data["type"] == "large_airport").sum()

    columns = st.columns(4)
    figures = [
        ("Airfields", f"{total:,}", "every kind, worldwide"),
        ("Countries", f"{countries_covered:,}", "with at least one"),
        ("Bookable", f"{with_iata:,}", "have an IATA code"),
        ("Large airports", f"{large:,}", "only 1 in 93"),
    ]
    for column, (label, value, note) in zip(columns, figures):
        column.markdown(
            f"<div class='stat'><div class='stat-label'>{label}</div>"
            f"<div class='stat-value'>{value}</div>"
            f"<div class='stat-note'>{note}</div></div>",
            unsafe_allow_html=True,
        )

    st.divider()

    left, right = st.columns([3, 2], gap="large")
    with left:
        # [PY1] first call, using the default count of 10.
        st.pyplot(draw_top_countries(data, 10), width="stretch")
    with right:
        st.markdown("#### Why the United States runs away with it")
        st.write(
            "The gap is not really about aviation. The American registry records "
            "private grass strips and hospital helipads that most national "
            "registries never list, so the count measures how thoroughly a country "
            "documents its airfields as much as how many it has."
        )
        st.info("Switch to **One country** in the sidebar to see how the ranking "
                "changes once only large airports are counted.")

    st.divider()

    # [DA6] Analyse the data with a pivot table.
    pivot = pd.pivot_table(
        data, index="continent_name", columns="type", values="ident",
        aggfunc="count", fill_value=0,
    )
    st.pyplot(draw_type_mix(pivot), width="stretch")
    st.caption(
        "Small airports and heliports dominate every continent. Fewer than "
        f"{large:,} airfields in the entire world are classed as large."
    )
    with st.expander("The pivot table behind this chart"):
        st.dataframe(pivot, width="stretch")


def page_country(data):
    """Second page: one country at a time, with its own chart, table and map."""

    # [ST1] A dropdown for the country.
    country_list = sorted(data["country_name"].dropna().unique())
    chosen_country = st.sidebar.selectbox(
        "Country", country_list, index=country_list.index("United States"))

    # [ST2] A multi-select for the airport types.
    type_options = sorted(data["type"].unique())
    chosen_types = st.sidebar.multiselect(
        "Airport types", type_options,
        default=["large_airport", "medium_airport"],
        format_func=lambda code: code.replace("_", " ").title())

    if not chosen_types:
        st.warning("Pick at least one airport type in the sidebar.")
        return

    # [PY3] second call site.
    selected = filter_airports(data, country=chosen_country, types=chosen_types)
    if selected.empty:
        st.info(f"No airports of those types are recorded for {chosen_country}.")
        return

    # [PY2] unpacking the three values the function returns.
    highest, lowest, average = elevation_extremes(selected)

    columns = st.columns(3)
    stats = [("Matching airfields", f"{len(selected):,}", chosen_country)]
    if highest is not None:
        stats.append(("Highest", f"{highest['elevation_ft']:,.0f} ft", highest["name"]))
        stats.append(("Lowest", f"{lowest['elevation_ft']:,.0f} ft", lowest["name"]))
    for column, (label, value, note) in zip(columns, stats):
        column.markdown(
            f"<div class='stat'><div class='stat-label'>{label}</div>"
            f"<div class='stat-value'>{value}</div>"
            f"<div class='stat-note'>{note}</div></div>",
            unsafe_allow_html=True,
        )
    if highest is not None:
        st.caption(f"Average elevation across this selection: {average:,.0f} ft.")

    st.divider()

    map_tab, mix_tab, rank_tab, table_tab = st.tabs(
        ["Where they are", "What mix", "How the country ranks", "The ten highest"])

    with map_tab:
        st.pydeck_chart(draw_map(selected))
        map_legend()
        st.caption("Hover a dot for the airport's name, town, type and elevation.")

    with mix_tab:
        # [PY3] fourth call site. This one deliberately drops the type filter, so
        # the pie always shows the country's whole make-up rather than only the
        # slice the user is currently looking at.
        everything_here = filter_airports(data, country=chosen_country)
        left, right = st.columns([3, 2], gap="large")
        with left:
            st.pyplot(draw_type_share(everything_here, chosen_country),
                      width="stretch")
        with right:
            st.markdown("#### Reading this chart")
            biggest = everything_here["type"].value_counts()
            share = biggest.iloc[0] / len(everything_here) * 100
            st.write(
                f"{biggest.index[0].replace('_', ' ').title()} is the largest "
                f"category in {chosen_country}, at {share:.1f}% of its "
                f"{len(everything_here):,} recorded airfields. That slice is "
                "pulled away from the centre so it is obvious at a glance."
            )
            st.caption(
                "Unlike the other tabs, this one ignores the type filter — it "
                "shows the whole country so the proportions still add to 100%."
            )

    with rank_tab:
        # [PY1] second call, passing the count instead of taking the default.
        st.pyplot(
            draw_top_countries(filter_airports(data, types=chosen_types), 15,
                               highlight=chosen_country),
            width="stretch")
        st.caption(f"{chosen_country} is picked out in orange, if it makes the top 15.")

    with table_tab:
        # [DA2] Sort by two columns at once. [DA8] Walk the rows with iterrows() to
        # build a readable summary. It runs on the top ten rows only, because
        # iterrows() is slow and there is no reason to walk 57,000 rows.
        ranked = selected.sort_values(
            ["elevation_ft", "name"], ascending=[False, True]).head(10)
        summary_rows = []
        for _, row in ranked.iterrows():
            summary_rows.append({
                "Airport": row["name"],
                "Town": row["municipality"] or "unknown",
                "Type": row["type_label"],
                "Elevation (ft)": row["elevation_ft"],
            })
        st.dataframe(pd.DataFrame(summary_rows), width="stretch", hide_index=True)


def page_elevation(data):
    """Third page: elevation, filtered by continent and by a height band."""

    # [PY5] again: the dictionary's items() feeds the continent dropdown.
    continent_choices = {code: name for code, name in CONTINENT_NAMES.items()}
    picked_name = st.sidebar.selectbox(
        "Continent", sorted(continent_choices.values()), index=3)
    picked_code = [code for code, name in continent_choices.items()
                   if name == picked_name][0]

    # [ST3] Sliders for the elevation band and for how fine the histogram should be.
    lowest_possible = int(data["elevation_ft"].min())
    highest_possible = int(data["elevation_ft"].max())
    band = st.sidebar.slider(
        "Elevation range (ft)", lowest_possible, highest_possible,
        (0, 8000), step=100)
    bins = st.sidebar.slider("Histogram detail", 10, 80, 40, step=5)

    # [PY3] third call site, this time with two filters at once.
    selected = filter_airports(data, continent=picked_code, elevation_range=band)
    if selected.empty:
        st.info("Nothing falls in that band. Widen the range in the sidebar.")
        return

    highest, lowest, average = elevation_extremes(selected)
    columns = st.columns(3)
    for column, (label, value, note) in zip(columns, [
        ("In this band", f"{len(selected):,}", f"{picked_name}, "
                                               f"{band[0]:,}–{band[1]:,} ft"),
        ("Highest here", f"{highest['elevation_ft']:,.0f} ft", highest["name"]),
        ("Lowest here", f"{lowest['elevation_ft']:,.0f} ft", lowest["name"]),
    ]):
        column.markdown(
            f"<div class='stat'><div class='stat-label'>{label}</div>"
            f"<div class='stat-value'>{value}</div>"
            f"<div class='stat-note'>{note}</div></div>",
            unsafe_allow_html=True,
        )

    st.divider()

    spread_tab, scatter_tab = st.tabs(["How they spread out", "Height against latitude"])

    with spread_tab:
        st.pyplot(draw_elevation_histogram(selected, bins), width="stretch")
        st.caption(
            "The mean sits to the right of the median because a small number of "
            "very high airfields pull it there. That gap is the shape of the "
            "distribution."
        )

    with scatter_tab:
        st.plotly_chart(draw_height_against_latitude(selected, picked_name),
                        width="stretch")
        st.caption(
            "Hover any dot to name the airport. Drag a box to zoom into a mountain "
            "range, click a legend entry to hide that category, and double-click "
            "the plot to reset it. The dotted line is sea level."
        )

    st.divider()

    # [DA5] Filter on two conditions joined by OR: the airfields at either extreme.
    # This deliberately ignores the slider band and looks at the whole continent,
    # because the interesting cases sit outside whatever range the user picked.
    whole_continent = filter_airports(data, continent=picked_code)
    unusual = whole_continent[(whole_continent["elevation_ft"] < 0) |
                              (whole_continent["elevation_ft"] > 10000)]
    st.markdown(f"#### The extremes of {picked_name}")
    st.write(
        "Airfields below sea level or above 10,000 feet — the ones the slider "
        "above normally hides."
    )
    if unusual.empty:
        st.info(f"{picked_name} has no airfield below sea level or above 10,000 ft.")
    else:
        st.dataframe(
            unusual[["name", "municipality", "country_name", "type_label",
                     "elevation_ft"]]
            .rename(columns={"name": "Airport", "municipality": "Town",
                             "country_name": "Country", "type_label": "Type",
                             "elevation_ft": "Elevation (ft)"})
            .sort_values("Elevation (ft)"),
            width="stretch", hide_index=True,
        )


def page_styles():
    """[ST4] The stylesheet that turns the default Streamlit page into a designed one."""
    st.markdown(
        f"""
        <style>
        .block-container {{ padding-top: 2.2rem; max-width: 1180px; }}
        h1, h2, h3, h4 {{ color: {INK}; letter-spacing: -0.015em; }}

        .hero-title {{
            font-size: 2.35rem; font-weight: 700; color: {INK};
            margin-bottom: .15rem; letter-spacing: -0.03em;
        }}
        .hero-sub {{
            font-size: 1rem; color: {MUTED}; margin-bottom: 1.6rem;
            border-left: 3px solid {PRIMARY}; padding-left: .8rem;
        }}
        .lede {{ font-size: 1.02rem; line-height: 1.65; color: #33475b;
                 margin-bottom: 1.5rem; }}

        .stat {{
            background: linear-gradient(180deg, #f7fbfd 0%, #eef6fa 100%);
            border: 1px solid #dceaf2; border-radius: 12px;
            padding: 1rem 1.1rem; height: 100%;
        }}
        .stat-label {{ font-size: .74rem; text-transform: uppercase;
                       letter-spacing: .09em; color: {MUTED}; font-weight: 600; }}
        .stat-value {{ font-size: 1.85rem; font-weight: 700; color: {INK};
                       line-height: 1.15; margin: .18rem 0 .1rem; }}
        .stat-note {{ font-size: .78rem; color: {MUTED}; line-height: 1.35; }}

        .legend {{ display: flex; flex-wrap: wrap; gap: .55rem .95rem;
                   margin: .5rem 0 .2rem; }}
        .key {{ font-size: .76rem; color: {MUTED}; display: flex;
                align-items: center; }}
        .key i {{ width: 11px; height: 11px; border-radius: 3px;
                  display: inline-block; margin-right: .35rem; }}

        section[data-testid="stSidebar"] {{ background: #f7fafc;
                                            border-right: 1px solid #e4edf3; }}
        section[data-testid="stSidebar"] h2 {{ font-size: 1.05rem; }}
        [data-testid="stMetricValue"] {{ color: {INK}; }}
        hr {{ margin: 1.6rem 0; border-color: #e6eef4; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def main():
    # [ST4] Customised page design: page title and icon, a wide layout, every
    # control kept in the sidebar, a matched colour theme in .streamlit/config.toml,
    # and the stylesheet above for the headings, stat cards and map legend.
    st.set_page_config(page_title="Airports of the World",
                       page_icon="✈️", layout="wide")
    page_styles()
    style_charts()

    data, dropped = load_data()

    st.sidebar.markdown("## ✈️ Airports")
    page = st.sidebar.radio(
        "View", ["Overview", "One country", "Elevation"], label_visibility="collapsed")
    st.sidebar.divider()

    subtitles = {
        "Overview": "What the world's 57,421 airfields actually look like",
        "One country": "Pick a country and see its airfields on the map",
        "Elevation": "How high airports sit, and the ones that break the pattern",
    }
    st.markdown(
        f"<div class='hero-title'>Airports of the World</div>"
        f"<div class='hero-sub'>{subtitles[page]}</div>",
        unsafe_allow_html=True,
    )

    if page == "Overview":
        page_overview(data)
    elif page == "One country":
        page_country(data)
    else:
        page_elevation(data)

    st.sidebar.divider()
    st.sidebar.caption(
        f"{len(data):,} airfields from OurAirports, joined to the Wikipedia "
        "ISO country list. Built with Streamlit, pandas, NumPy, Matplotlib, "
        "Plotly, PyDeck and pycountry."
    )
    if dropped:
        st.sidebar.caption(
            f"{dropped} rows were set aside as physically impossible - an "
            "airfield at the North Pole, and an advertisement filed as a large "
            "airport. The source CSV is unaltered; the filtering happens in "
            "memory. See drop_impossible_records() for the two tests used."
        )


main()
