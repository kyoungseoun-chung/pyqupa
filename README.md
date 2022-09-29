# Currently, the code is in alpha stage. Heavly under development! (Only a portion of web data is stored in `pypass/db` at this moment.)
# PYPASS: Python wrapper for [quaeldich.de](https://www.quaeldich.de)

A Python interface to access data in [quaeldich.de](https://www.quaeldich.de).

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://kyoungseoun-chung-pypass-pypassapp-xwr7oa.streamlitapp.com/)

## Installation

Install from source:
We use `poetry` to manage all dependencies.
- `git clone git@github.com:kyoungseoun-chung/pypass.git`
- `poetry install`

## How it works

[Quaeldich.de](https://www.quaeldich.de) stores all mountain pass data in json files with unique data-ids. For example, **Mont Ventoux** approaching from **Bédoin** has geopositioning data (latitude, longitude, elevation, and distance) identified by `data-id=127_189`. Therefore, data can be accessed via the URL `https://www.quaeldich.de/qdtp/anfahrten/127_189.json`. We scraped all pass data URLs from the website and saved them in `pypass/db/passes.json`. Whenever you attempt to search for pass information, the code will first look for the URL and process data for you.


## Basic usage

**Warning**: search by region is not working properly!

```python
>>> from pypass.passees import PassDB
>>> passdb = PassDB()
>>> passdb.search("Mont Ventoux", "name")
# List of a Pass with length == 1
[Pass(name='Mont Ventoux', coord=[44.1736, 5.27879], ...)]
>>> passdb.search("italien alpen", "region") # Not working at this point...
>>> passdb.search([1800, 2000], "height")
>>> passdb.search([10.0, 15.0], "distance")
>>> passdb.search([500, 1000], "elevation")
# List of Passes matching criteria either "region", "height", "distance", or "elevation".
[Pass(name='Mont Ventoux', coord=[44.1736, 5.27879], ...), Pass(...), ...]
```

## Features

### Extract data

- You can use cli command to extract data from quaeldich.de.
    - You need two arguments `-e` and `-d`.
    - If you set give 0 for `-e`, it will extract all data registered in quaeldich.de.
    - If you don't set `-d` option, it will save db to `pypass/db/`.
    - DB doesn't contain geopositioning data. Only relevant URLs to be processed later on.

- Mac OS or Linux
    ```zsh
    python -m pypass -e NUMBER_OF_PASS_TO_BE_EXTRACTED -d DIRECTORY_TO_BE_SAVE_DB
    ```
- Windows
    ```zsh
    py -m pypass -e NUMBER_OF_PASS_TO_BE_EXTRACTED -d DIRECTORY_TO_BE_SAVE_DB
    ```

### Search and access Pass data

- You can search Pass data by region, name, height, distance, and elevation gain.

- Each `Pass` class contains all paths to the top including information regarding distance, elevation, and gradient.
```python
>>> from pypass.passees import PassDB
>>> passdb = PassDB()
>>> Pass = passdb.search("Mont Ventoux", "name")  # Always return list[Pass]
>>> Pass[0].path_names
['South Side from Bédoin', 'West Side from Malaucène', 'East Side from Sault']
# Mont Ventoux has 3 access points.
>>> Pass[0].total_distance
[21169.514785722, 20846.819408688, 25365.999999999996]  # in meter
>>> Pass[0].total_elevation
[1592.295991259, 1572.2721899565, 1152.0] # in meter
>>> Pass[0].avg_grad
[7.521646137742093, 7.5420243209918585, 4.54151226050619] # in %
>>> Pass[0].elevation
[array([ 313, ..., 1905.29599126]), ...]
# GPT log data for the elevation in meter (from start to end)
```

- Name suggestion for a typo when searching the pass.
```python
>>> from pypass.passees import PassDB
>>> passdb = PassDB()
>>> Pass = passdb.search("Mont Venoux", "name") # Wrong input name
...
NameError: The given name (Mont Ventox) is not in our database. Did you mean ['Mont Ventoux']?
# Raise `NameError` and will give name suggestion for the close match.
```


### Running GUI

We created GUI using [steamlit](https://streamlit.io). You can run GUI by typing following command:
```zsh
python -m streamlit run pypass/app.py
```

Or access via [URL](https://kyoungseoun-chung-pypass-pypassapp-xwr7oa.streamlitapp.com/)

#### Demos:

* Search by name:
![search by name](.pypass/../pypass/assets/screenshots/search_by_name.png)
* Search by distance:
![search by name](.pypass/../pypass/assets/screenshots/search_by_distance.png)


### Current issues/WIPs

Below is the list of issues or WIPs.

#### Data exception handling
- [ ] Empty Pass basic data.
- [ ] Empty geopositioning data.
- [ ] Non-empty geopositioning data but with empty string.

#### Better data process
- [ ] Elaborate gradient computation.

#### GUI app
- [ ] Pass search options.
- [ ] Change plots from `matplotlib` to `plotly`.
