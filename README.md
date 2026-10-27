# methane-s5p-explorer

[![CI](https://github.com/OWNER/methane-s5p-explorer/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/methane-s5p-explorer/actions/workflows/ci.yml)

A small exploration of Sentinel-5P TROPOMI methane (XCH4) over western Turkmenistan, a known
methane hotspot, using the Google Earth Engine Python API. It makes two figures: a map of where the
three-year mean XCH4 sits above or below the regional median, and a monthly time series.

It is an exploration, not an emissions analysis. The [Limitations](#limitations) section explains why.

## What TROPOMI XCH4 is

[TROPOMI](https://sentinels.copernicus.eu/web/sentinel/missions/sentinel-5p) is the spectrometer on
the Copernicus Sentinel-5 Precursor satellite. It measures sunlight reflected by the Earth's surface
in the shortwave infrared, where methane absorbs, and covers almost the whole planet every day.

From those spectra the retrieval estimates **XCH4, the column-averaged dry-air mole fraction of
methane**. It is the average methane concentration in the whole column of air between the surface
and the top of the atmosphere, with water vapour taken out, in **parts per billion (ppb)**.
The pixels are about **7 x 5.5 km** at nadir.

This repo uses Earth Engine's Level 3 product,
[`COPERNICUS/S5P/OFFL/L3_CH4`](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_OFFL_L3_CH4).
Earth Engine keeps retrievals with a quality value of at least 50% and regrids them to 0.01°
(about 1.1 km). The regridding does not add detail. Each value still comes from a ~7 km measurement.

## What the script does

[`src/explore_xch4.py`](src/explore_xch4.py) selects the XCH4 band for January 2023 to December 2025
over a 3° x 3° box (52.5-55.5°E, 37.5-40.5°N) and then:

1. **Anomaly map.** Averages every valid retrieval per pixel over the three years, samples the mean
   onto a 0.05° grid, and subtracts the median of all pixels in the box. Red is above the regional
   median and blue is below it. Hatching marks pixels with no valid retrievals at all.
2. **Monthly series.** For each month, takes the mean XCH4 over the box and the mean number of valid
   retrievals per pixel, which shows how much data each month actually had.

<!-- FIGURES -->

## How to run it

You need a Google Cloud project registered for Earth Engine (free for noncommercial use, see
[Earth Engine access](https://developers.google.com/earth-engine/guides/access)).

### With pip

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

earthengine authenticate           # once per machine; opens a browser
export EE_PROJECT=your-project-id  # PowerShell: $env:EE_PROJECT = "your-project-id"
python src/explore_xch4.py         # writes the three files in outputs/

pytest                             # unit tests, no Earth Engine needed
ruff check . && ruff format --check .
```

### With Docker

The image installs `requirements.txt` on `python:3.12-slim` and runs the tests by default:

```bash
docker build -t methane-s5p-explorer .
docker run --rm methane-s5p-explorer
```

To run the exploration itself in the container, pass in your project ID and your existing Earth
Engine credentials (mounted read-only), and mount `outputs/` so the files land on your machine:

```bash
docker run --rm \
  -e EE_PROJECT=your-project-id \
  -v ~/.config/earthengine:/root/.config/earthengine:ro \
  -v "$(pwd)/outputs:/app/outputs" \
  methane-s5p-explorer python src/explore_xch4.py
```

## Tests and CI

[`tests/test_logic.py`](tests/test_logic.py) covers the parts that don't need Earth Engine: the month
list, the anomaly maths, turning Earth Engine's output into a dataframe (including months with no
data), and the two plotting functions.

[GitHub Actions](.github/workflows/ci.yml) runs on every push and pull request. It installs the
requirements, runs `ruff check`, `ruff format --check` and `pytest`, then builds the Docker image and
runs the tests inside it. CI makes no Earth Engine calls and holds no credentials.

## Limitations

**Coarse pixels can't resolve individual plumes.** A methane plume from a single well pad,
compressor station or pipeline leak is usually tens to hundreds of metres wide. Inside a ~7 x 5.5 km
TROPOMI pixel it is diluted into the background, so the pixel shows a small rise in XCH4 rather
than a plume with a clear origin. Only very large releases stand out in a single overpass. That is
why point-source detection uses high-resolution sensors with pixels of tens of metres. Examples are
hyperspectral imagers such as PRISMA, EnMAP and EMIT, and multispectral ones such as Sentinel-2 and
Landsat. UNEP's [Methane Alert and Response System](https://methanedata.unep.org/methane-alert-response-system)
works in tiers: TROPOMI screens wide areas and flags hotspots, and high-resolution imagers then
attribute plumes to facilities. This repo only does the first, coarse step, and only roughly.

**Clouds and surface albedo cause gaps.** The retrieval needs clear sky and enough reflected
sunlight. Clouds block the view, and dark surfaces such as water reflect too little shortwave
infrared, so those retrievals are filtered out. Bright or varied surfaces can bias XCH4 even when
retrievals pass the filter. The Earth Engine product also has an albedo-bias-corrected band
(`CH4_column_volume_mixing_ratio_dry_air_bias_corrected`), which would be a better choice for
comparing pixels over very different surfaces. This script uses the standard band.

**The anomaly is a simple comparison with the regional median, not an emission estimate.** A pixel
above the median may be near a source, but it can also reflect wind carrying methane in or out,
retrieval artefacts, or the choice of box. Topography matters too. Over high ground the air column
is shorter, so the methane-poor stratosphere makes up more of it and XCH4 reads lower. Turning
enhancements into emission rates (tonnes per hour) needs wind data and a quantification method such
as a mass balance or an atmospheric inversion, none of which this repo attempts.

**The monthly series mixes several signals.** The regional mean combines the global upward trend in
methane, the seasonal cycle, and changes in which parts of the box had valid data that month. Months
with few retrievals are not like-for-like with well-sampled months.

## Licence

[MIT](LICENSE)
