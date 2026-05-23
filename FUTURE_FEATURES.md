# Future Features & Expansions

## Find Places

- **More reviews via newer API**: Switch the `GET /places/{place_id}/details` endpoint from the legacy Places API to the new `places.googleapis.com/v1` API, which supports `reviews_sort=newest` to return the 5 most recent reviews instead of Google's "most relevant" selection. Requires refactoring the URL, auth header format, and response schema parsing.
