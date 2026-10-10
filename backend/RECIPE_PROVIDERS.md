# Recipe Providers

Set `AI_PROVIDER` in the backend environment to `local`, `themealdb`,
`spoonacular`, `api`, or `mock`. The default `local` provider retrieves recipes
from the project's own small recipe corpus and classifies known ingredient
aliases using a local Spanish/English taxonomy. It needs no API key, paid
service, hosted model, embeddings, or network access. This is lightweight
structured RAG, not semantic vector search; expand the taxonomy and authored
recipe corpus as product coverage grows.

`themealdb` uses `THEMEALDB_API_KEY`; key `1` is for development and educational
use. Publicly released apps should obtain the appropriate production access from
TheMealDB. `spoonacular` requires `SPOONACULAR_API_KEY`; its available free quota
and endpoint costs depend on the account, so check the current dashboard before
relying on it in production.

TheMealDB's free filter supports one pantry ingredient per search. It does not
provide nutrition data or preparation time in the recipe response; this adapter
uses `calorias: 0` to mean unavailable and a 30-minute estimate to satisfy the
existing response contract. The local corpus also uses `calorias: 0` because it
does not yet include verified nutrition facts. Spoonacular returns the recipe's
reported time, servings, and calories when provided. All providers still pass
through the backend's deterministic allergen filter.

The public recipe response remains unchanged. Before publishing recipe data or
images, provide the attribution required by the selected provider in the client
and review that provider's current terms.