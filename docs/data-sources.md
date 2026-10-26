# Data sources and attribution

- **Live input:** [SWAPI](https://swapi.dev/), via its documented [people and starship endpoints](https://swapi.dev/documentation). Each run downloads upstream JSON into the local, ignored `artifacts/` directory. Live data is not redistributed as a bundled dataset.
- **Offline fixture:** original synthetic data in `src/starship_pipeline/demo.py`. Ari Vale, Mira Chen, Sol Reed, Aurora, Horizon and Relay are fictional test records. Their resource URLs follow the SWAPI shape solely so the same identity checks run in tests; the fixture does not claim those invented IDs exist on SWAPI.
- **Published live evidence:** `examples/live-verification.json` contains counts, quality outcomes, provenance and one short factual pilot-link example from the observed run. It excludes raw upstream record dumps, credentials, local machine paths and MongoDB ObjectIds.
- **Excluded:** classroom datasets, trainer messages, private repository history, screen recordings, personal contact details and local configuration.

The project's MIT license covers its code, documentation and original fixtures. It does not grant rights to upstream content or Star Wars names and trademarks. This portfolio project is unaffiliated with the owners of those properties.
