# 0006 — A managed skill catalogue with a normalised key

Status: accepted, supersedes free-text skill names

## Context

At first, assigning a skill created it if its name was new, unique ignoring
case only. That fills the database with near-duplicates — `Node.js`, `NodeJS`,
`node js` — and a search for one does not find employees who have the others,
which defeats the purpose of the application.

## Decision

- **Skills come from a catalogue.** The catalogue page adds, renames and
  removes skills, and imports a CSV of names. Everywhere else, skills are chosen
  from the catalogue's suggestions; typed text that is not a suggestion is
  neither assigned nor searched for, and the API assigns skills by id only.
- **Names are unique by a normalised key**: case folded, `+` and `#` spelled
  out as `plus` and `sharp`, everything but letters and digits removed. So
  `Node.js` = `nodejs` = `Node JS`, while `C`, `C++` and `C#` stay apart. The
  key is a column with a unique index, so concurrent requests cannot create
  the same skill twice (`INSERT … ON CONFLICT DO NOTHING`), and the catalogue
  search and the employee search match by the same key.
- **Renaming** changes the name for everyone who has the skill; renaming into
  an existing skill is refused, not merged. **Removing** is only possible while
  nobody has the skill.

## Alternatives

- **Free text with fuzzy matching**: would merge skills that are different
  (Java and JavaScript) and still miss others; a wrong merge is worse than a
  duplicate.
- **A fixed list in the code**: every new skill would need a release.
- **Merging skills**: useful for cleaning up a catalogue that has already
  drifted; left out until that happens, since a strict catalogue prevents it.

## Consequences

- Someone has to look after the catalogue, and a missing skill has to be added
  before it can be assigned; the skill input links to the catalogue page.
- The migration to the key refuses to run while existing skills would collide
  ([0002](0002-reviewed-migrations.md)); they are renamed or removed first.
