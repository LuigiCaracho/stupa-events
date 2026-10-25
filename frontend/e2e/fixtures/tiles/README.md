Test tiles for the map specs, cut from the real archives with `pmtiles extract` (pmtiles 1.31.2, build 20261024):
`world.pmtiles` is the world to zoom 2, `reutlingen.pmtiles` the box 9.15,48.47,9.25,48.52 to zoom 10. They are
checked in so CI never loads the network; the real files come from `scripts/build-tiles.sh`.
