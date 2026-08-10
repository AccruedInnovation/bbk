# Bundled BBK language profiles

BBK `0.1.0-alpha.17.0.2.1` includes independently versioned Go, Python, Rust, and TypeScript/JavaScript profile packages at `0.1.0-alpha.3`. They install by default unless `--no-language-profiles` is supplied. Profile registries may declare required and optional procedures; the host-neutral compiler binds selected procedure IDs and the profile-registry revision into the effective child prompt and invalidation state.

Each inner ZIP is independently manifested and strictly verified after this outer bundle is verified. The profile compatibility floor is BBK `0.1.0-alpha.8`; legacy `bbk_version: 0.1.0-alpha.4` projection values identify the structure/slice contract dialect rather than the installed core version or the profile package version.

Each inner archive retains its own release identity and manifest. `RELEASE-MANIFEST.json` records the exact inventory. Package versions must be read from each profile's own `PROFILE.json` and `VERSION`; they are not inferred from the outer BBK release number.
