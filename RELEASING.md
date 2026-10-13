# Releasing

`cyborg-data` ships two packages that version **independently** via Git tags:

| Package | Location | Tag prefix  | Version source                         |
|---------|----------|-------------|----------------------------------------|
| Go      | `go/`    | `go/`       | `go/version.go` (`Version` const)      |
| Python  | `python/`| `python/`   | `python/pyproject.toml` (`version`)    |

Both follow [Semantic Versioning](https://semver.org/). There is no package
index or image pipeline — consumers pull a tagged commit directly from Git.

> **Why the tag prefix matters (Go):** the module path is
> `github.com/openshift-eng/cyborg-data/go`, a *subdirectory* module. Go only
> resolves versions for a subdirectory module from tags prefixed with that
> subdirectory, i.e. `go/vX.Y.Z`. A bare `vX.Y.Z` tag is **not** seen by
> `go get` for this module.

## Release steps

Releases are cut from `main` after the normal Prow merge flow
(`/lgtm` + `/approve` from [`OWNERS`](./OWNERS), merged by Tide).

1. **Open a release PR** that:
   - bumps the version — Go: the `Version` const in `go/version.go`; Python: the
     `version` in `python/pyproject.toml` (and `python/orgdatacore/_version.py`
     if it duplicates it);
   - promotes the package's `CHANGELOG.md` `[Unreleased]` section to a new
     `[X.Y.Z] - YYYY-MM-DD` heading.
2. Get it reviewed and merged (`/lgtm`, `/approve` → Tide).
3. **Tag the merge commit on `main`** and push the tag:

   ```bash
   git checkout main && git pull
   # Go release:
   git tag go/v0.2.0 && git push origin go/v0.2.0
   # Python release:
   git tag python/v1.1.0 && git push origin python/v1.1.0
   ```
4. **Create a GitHub Release** from the tag (optional but recommended) and paste
   that version's changelog section as the notes.

Only tag the package(s) that actually changed — the two version lines move
independently.

## Consuming a release

**Go** — the module version is the tag minus its `go/` prefix:

```bash
go get github.com/openshift-eng/cyborg-data/go@v0.2.0
```

**Python** — install from the tag; the package lives in the `python/`
subdirectory:

```bash
pip install "orgdatacore @ git+https://github.com/openshift-eng/cyborg-data.git@python/v1.1.0#subdirectory=python"
```

## Note on the legacy `v0.1.0` tag

The existing `v0.1.0` tag predates this scheme and is **not** on a `go/` or
`python/` prefix, so `go get` cannot use it for the `/go` module. Going forward,
use the prefixed tags above. Cleaning up or re-pointing the old tag is optional
and left to the maintainers.
</content>
