# Currently, the code is in alpha stage. Heavly under development!
# PYPASS: Python wrapper for [quaeldich.de](https://www.quaeldich.de)

A Python interface to access data in [quaeldich.de](https://www.quaeldich.de).

## Installation

Install from source:
We use `poetry` to manage all dependencies.
- `git clone `
- `poetry install`

## How it works

[Quaeldich.de](https://www.quaeldich.de) stores all mountain pass data in json files with unique data-ids. For example, **Mont Ventoux** approacing from **Bédoin** has geopositioning data (latitude, longitude, elevation, and distance) identified by `data-id=127_189`. Therefore, data can be accessed via the URL `https://www.quaeldich.de/qdtp/anfahrten/127_189.json`. We scraped all pass data URLs from the website and saved them in `pypass/db/passes.json`. Whenever you attempt to search for pass information, the code will first look for the URL and process data for you.


## Usage

Mountain pass can be searched by region, name, height, distance (WIP), and elevation gain(WIP).

```python
>>> from pypass.quaeldich import search_pass_by_name
>>> Pass = search_pass_by_name("Mont Ventoux")
>>> Pass = search_pass_by_height([1000, 2000])
```

## Features

### Search mountain pass data

- It contains all paths to the top including information regarding distance, elevation, and gradient.
```python
>>> from pypass.quaeldich import search_pass_by_name
>>> Pass = search_pass_by_name("Mont Ventoux")
>>> Pass.path_names
['South Side from Bédoin', 'West Side from Malaucène', 'East Side from Sault']
# Mont Ventoux has 3 access points.
>>> Pass.total_distance
[21169.514785722, 20846.819408688, 25365.999999999996]  # in meter
>>> Pass.total_elevation
[1592.295991259, 1572.2721899565, 1152.0] # in meter
>>> Pass.avg_grad
[7.521646137742093, 7.5420243209918585, 4.54151226050619] # in %
>>> Pass.elevation
[array([ 313. ...29599126]), array([ 334. ...27218996]), array([ 757. ... ])]
# GPT log data for the elevation in meter (from start to end)
```

- Name suggestion for a typo when searching the pass.
```python
>>> from pypass.quaeldich import search_pass_by_name
>>> Pass = search_pass_by_name("Mont Venoux") # Wrong input name
The given name (Mont Vento) is not in our database. Did you mean ['Mont Ventoux']?
# Name suggestion for the close match. 
```


### GUI using [steamlit](https://streamlit.io)

You can run GUI by typing following command:
```python
>>> python -m streamlit run pypass/app.py
```


## WIP:
- Pass data
    - [ ] Elaborate gradient computation.
    - [ ] Search pass data by path distance and elevation gain.
- GUI using Streamlit.
    - [ ] Better gradient profile.
    - [ ] Change plot engine from matplotlib to plotly.
