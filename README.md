# Job Finder

Job Finder keeps a structured professional profile in Odoo, imports it from a PDF CV, prints it as a complete CV,
and publishes it as a bilingual portfolio website.

## Structured profile

A profile (`job.profile`) holds the identity and contact details (name, headline, photo, location, email, phone,
LinkedIn, GitHub, website, summary) and these records, each with a sequence and a **Show on portfolio** flag:

| Model | Content |
| --- | --- |
| `job_finder.experience` | Roles: professional experience or academic research, with company, location, start and end (or *I currently work here*, or *Show years only*), employment type, description, highlights (one per line), and **Show as secondary** (listed in the portfolio's collapsible group of other experience). |
| `job_finder.project` | Projects, usually inside a role: subtitle (client or short description), description, technologies, link, and **Featured** (listed in the portfolio's Selected work, with a case-study page). The **Case study** tab adds an area, platforms, a cover image, *What I built* (one item per line, `Title: description`), key outcomes (`job_finder.project_metric`: value and label) and architecture steps (`job_finder.project_step`). |
| `job_finder.profile_figure` | Key figures shown under the portfolio's introduction, for example *55k+ App downloads*. |
| `job_finder.technology` | Technologies and methods shared by projects and skill groups (Job Finder › Configuration › Technologies). |
| `job_finder.skill_group` | Skill areas, each with its technologies. |
| `job_finder.education` | Qualifications: code, institution, location, years, status. |
| `job_finder.training` | Trainings, licences and credentials: issuer, year, status. |
| `job_finder.volunteering` | Leadership and volunteering: organisation, location, period, highlights, roles and recognition. |
| `job_finder.spoken_language` | Languages with their level (A1–C2 or native). |

Headline, location, summary, roles, project names and descriptions, highlights and the other texts are
translatable: write them once per language with Odoo's translation button, and the portfolio and the CV follow the
visitor's or the report's language.

The form shows a **Profile completeness** bar with what is still missing (photo, dates of a role, language levels…).
Users reach only their own profile and its records; administrators reach all of them.

## Import from a CV

Upload a PDF CV in the **CV import** tab and click **Analyze CV**. The text of each section is extracted (contact
details, Summary, Experience, Academic research, Skills, Education, Trainings, Volunteering, Languages) and turned
into records:

- a title line followed by `Company | Location | Dates | Type` starts a role; `(continued)` roles merge into the
  previous one;
- a line followed by `Technologies / methods:` starts a project in the current role; bullets belong to the current
  project, or to the role's highlights before its first project;
- `Category: item, item` lines become skill groups; `Name | Issuer | Year | Status` lines become trainings;
- PDF line wrapping is joined back.

Pages are read in visual order (pypdf's layout mode), so bullets stay with their project even in PDFs that draw
every bullet after the titles of the page.

Analyzing replaces the entries of every section the CV contains (after a confirmation) and keeps the others.
The extracted text stays read-only in **CV import › Imported text**. Regression fixtures include the complete
six-page reference PDF, its extracted text and the expected values.

## Portfolio website

The module depends on Odoo's `website`. The portfolio is the page `/portfolio`, set as the website's homepage, so
`/` shows it (and `/es/` in Spanish). It follows the design in `ui/ui.pen` (desktop 1440, tablet 768 and mobile 390):

- **Introduction**: photo, availability and location, name, headline, tagline (the first sentence of the summary
  unless a tagline is set), links, and the key figures.
- **Selected work**: the featured projects; the first two as large cases with their first three key outcomes, the
  others as cards. Each opens its case-study page.
- **Experience**: the professional roles with their first highlight and their projects; roles shown as secondary are
  grouped in a collapsible row (*Other experience* unless the profile sets a title).
- **Skills**, **Background** (research and academic projects, education, leadership and volunteering, languages,
  training and credentials, with *more* toggles) and **Contact**.

Sections and navigation links appear only when they have entries shown on the portfolio. The large section
headlines default to the section names; set your own in the **Portfolio** tab. The toggles and the mobile menu use
HTML disclosure elements, without JavaScript.

### Case-study pages

Each featured project shown on the portfolio has a page at `/portfolio/project/<name>-<id>` (an older name
redirects to the current one): area, title, summary (the first sentence of the description), role, company, period
and platforms, cover, key outcomes, overview (the rest of the description), *What I built*, architecture, stack,
the project link, and the next case study. Sections without content are hidden. Other projects have no page, and
only the covers of these pages are public, at `/portfolio/project/<id>/cover`.

Architecture flows with four or more components stack vertically so longer pipelines remain readable without
horizontal scrolling on desktop, tablet and mobile.

The project covers in `ui/assets/cover-*.png` are AI-generated placeholders for the design; upload real screenshots
or photos as covers.

### Publishing

1. Complete the profile (or import the CV) and add a photo.
2. As an administrator, switch on **Publish as portfolio** next to the headline, and save.
3. Optionally, in the **Portfolio** tab: write a tagline, an availability note, the section headlines, the title of
   the secondary experience and the key figures; show the phone (hidden by default; it always appears in the
   complete CV); and adjust the search engine and sharing title, description and image (they default to the name
   and headline, the summary, and the photo).
4. For each featured project, fill in its **Case study** tab and upload a cover.

Only one profile can be published at a time.

### Languages and domain

Languages are the website's languages (Website › Configuration › Settings): the EN / ES links switch the whole page,
including the fixed texts from `i18n/es.po` and the translated profile texts. The domain is the website's
**Website Domain** setting; DNS, TLS and the reverse proxy are configured outside this module.

### Download CV

The navigation shows **Log in** (Odoo's login page) to visitors and **Open Odoo** (the backend) to internal users;
portal users, who have no backend, get no button there. **Download CV**, in Experience and Contact, opens
`/portfolio/cv`; for visitors who are not signed in it shows a lock. Anonymous visitors get a
sign-in page (Odoo's login form, returning to the download) with a link to request the CV by email; internal users
download the complete PDF; portal and other external accounts get a 403 page that suggests requesting it by email.
Only the published profile's photo is public, at `/portfolio/photo`.

## CV (PDF)

**Download CV** in the form header opens a dialog to choose CV areas, or none for the complete CV (Print ›
Complete CV gives the complete one). The PDF is A4, in one column built for applicant tracking systems: real text,
no images or layout tables, standard section names (Professional summary, Skills, Experience, Projects, Research and
academic projects, Education, Certifications and training, Leadership and volunteering, Languages) and dates
aligned on the right, with a violet accent. Entries hidden from the portfolio still appear in the CV. Profile access
rules apply to downloads.

### CV areas

The **CV areas** tab lists the areas you apply for, such as Frontend, Backend, DevOps or Hospitality, each with an
optional CV headline and summary (they replace the profile's). Tag roles, projects, skill groups, trainings and
volunteering with their areas in their tabs (`job_finder.cv_area`, *CV areas* field):

- untagged entries appear in every CV; tagged ones only in the CVs of their areas;
- a project without areas follows its role; a tagged project brings its role, with only the projects of the chosen
  areas;
- education and languages are always included;
- several areas can be combined, for example Frontend and Backend for a full-stack job.

On the portfolio, **Download CV** shows internal users a page to choose the areas when the profile has some
(`/portfolio/cv?download=1&area=<id>`); the file name includes the chosen areas.

## Upgrading to 19.0.1.2.0

A CV import marks professional roles without projects (production, hospitality…) as secondary. The migration to
19.0.1.2.0 applies the same rule to the existing roles; change **Show as secondary** on any role afterwards.

## Upgrading from 19.0.1.0.0

The migration to 19.0.1.1.0 builds the records from the text stored by earlier versions (only for profiles that
have no records yet), sets `/portfolio` as the website homepage when none is set, and removes the former
`job_finder.portfolio_hosts` parameter.

## Australian job search

Open Offers and choose **Propose searches** to create one editable search per existing
CV area. The proposal combines the area's name/headline, tagged role titles,
projects and technology names; repeated proposals preserve edits. Hospitality is
inactive; other areas are active. Searches default to Perth. Add comma-separated
cities, enable Australia-wide, or enable Remote (a `remote` keyword query).
Search now and the daily cron use the same ingestion and budget logic.

An administrator configures `job_finder.adzuna_app_id`,
`job_finder.adzuna_app_key` and `job_finder.adzuna_call_limit` (default 20) in
Settings > Technical > Parameters > System Parameters. Never put credentials in
source or preview data. Missing credentials give a configuration message without
making a request. Every attempted request consumes the shared run budget; errors,
HTTP 429 and exhausted budgets stop the run with credential-free diagnostics.
Persisted sequence order and per-search location cursors ensure later configurations
and modes progress. Each mode receives at most two pages per run.

The client uses the documented `what`, `where`, `results_per_page`, `app_id` and
`app_key` parameters on `/v1/api/jobs/au/search/{page}`. No salary, contract or
undocumented remote filter is sent. The profile's maximum age is applied locally
using the documented `created` timestamp. Distance is omitted pending verification.
The mapping uses only fields shown in the official
[Adzuna search documentation](https://developer.adzuna.com/docs/search);
the [interactive reference](https://developer.adzuna.com/activedocs) is linked
there. Adzuna returns a snippet, so eligibility checks cannot verify omitted text.
Each offer links to Adzuna and retains its provider link.

Scoring is deterministic: area/headline title match +30; matching technologies
+20 for roles current or ending within two years, +10 for older/undated projects,
+8 for skill-only technologies (technology total capped at 38); junior, graduate
or entry-level title +15; configured location match +10; visa sponsorship +7.
The additive breakdown is stored. Senior/lead/principal/head/manager/architect
titles and actual citizenship, PR or clearance obligations get score zero and
a discard reason. Negated, optional and descriptive mentions retain normal
scoring, including the three NV1 regression examples. Ambiguous wording is kept
for review. Score **>= threshold** qualifies as new/pending, independently of AI
availability; lower scores are stored as discarded. The profile defaults to a
subclass 485 visa with work rights through February 2028.

Offers are unique by profile and Adzuna ID. Repeated ingestion preserves the
original score/provenance, status, notes and evaluation. Saved, applied,
interview, offer, rejected and discarded are tracked in addition to new. Discard and Reject open a reason dialog; a reason is required before confirming. Status changes
are dated, and applied/interview transitions record their dates.

### Optional evaluator

Create a dedicated user in Settings > Users with only **Job Finder evaluator**;
do not grant Internal User or administrator groups. The evaluator group does not
imply Internal User and has no offer/search/profile CRUD access. Keep this account
separate from a profile owner. For ordinary internal users, Odoo documents key creation under Preferences >
Account Security > New API Key (description and expiry required). This restricted
account has no internal or portal ACLs, so an administrator must provision its key
in a controlled Odoo shell: find the evaluator user by login, then use
`env["res.users.apikeys"].with_user(evaluator_user).sudo()._generate(None,
"Job Finder evaluator", expiry_datetime)`. Elevated access here is needed only
to provision a key for the ACL-free service account; retain the evaluator as the
user context. Transfer the returned key directly to the evaluator's secret store,
never to source, logs or preview data. No key is generated by this module or seed.
Use a short expiry (at most 90 days) and rotate it before expiry.
Odoo external API access
on hosted plans requires a Custom plan. See the official
[Odoo 19 external API documentation](https://www.odoo.com/documentation/19.0/developer/reference/external_api.html).

Call only `job_finder.job_offer.evaluator_pending(limit)` (integer 1–100) and
`job_finder.job_offer.evaluator_store_result(offer_id, result)` through Odoo 19's JSON-2 API. For example, POST to
`/json/2/job_finder.job_offer/evaluator_pending` with JSON body `{"limit": 10}`;
POST to `/json/2/job_finder.job_offer/evaluator_store_result` with
`{"offer_id": 123, "result": {"ai_state": "done", "ai_score": 80, "ai_fit": "...",
"ai_gaps": "...", "ai_warnings": "..."}}`. Send the API key in the
`Authorization: bearer <API_KEY>` header and, where required, the database name in
`X-Odoo-Database`. Rotate expiring keys at least every three months. Pending payloads include id, title, snippet, rule score and
headline/areas/technologies/visa/location summary. Technology years merge known
role usage intervals across linked projects, counting overlaps once and retaining
gaps; unknown durations are null rather than invented.

`result` must contain exactly `ai_state` (`done` or `error`), `ai_score` (finite
number 0–100, never a boolean), and string `ai_fit`, `ai_gaps`, `ai_warnings`
(each at most 10000 characters). Non-pending, missing or invalid IDs and replay
submissions are refused. The form displays results read-only and shows **Not
evaluated** until a result is recorded. Other ordinary model operations require
normal ACLs; the evaluator receives none for these models.

For isolated preview only, execute `.hermes/preview-seed.py` in an Odoo shell
where `env` is provided. It creates reserved synthetic records idempotently and
never creates API keys or contacts Adzuna.

### Eligibility and location review corrections

Citizenship and permanent-residency obligations share the discard reason
**Australian citizenship or permanent residency required**. Full working rights
are an exemption only when listed as an alternative, such as "citizen, permanent
resident or have full work rights". They do not waive a requirement in "citizen
or permanent resident with full working rights" or "citizenship required,
applicants must also have full work rights".

Clearance levels Baseline, NV1, NV2, Negative Vetting (with or without level 1/2),
PV/Positive Vetting and
TSSC are recognised even without the word clearance when an obligation is
expressed. Examples include "Baseline required", "Must hold an NV1" and
"must hold or be able to obtain an NV1 security clearance". Conjunction lists
remain intact. Negated, waived, inapplicable, optional and descriptive references
retain normal scoring, including "requirement does not apply" and "has been
waived". Ambiguous snippets remain subject to heuristic limitations.

Location contributes 10 points for a complete normalised match on any configured
city against Adzuna's display name or location area. An unconfigured city earns
none. Australia-wide enables the location bonus for all offers returned by the
Australian endpoint; Remote enables it for a remote location/title/snippet.
A remote mention alone does not earn location points without that mode enabled.

Each search persists its next location-mode cursor. Runs rotate through the
configured cities, Australia-wide and Remote modes instead of restarting at
Perth. Searches themselves are served in persisted sequence order (including
when multiple runs happen within a second). A mode receives at most two pages
per run and each search receives one mode per round, preventing a busy city from
using all available pages. The cursor advances after each attempted request,
including provider errors; budget and HTTP rate-limit stops remain logged.
At budget one, every configured pair is reached within the number of active
searches times the largest number of modes. Pagination intentionally restarts
at page one when that mode is next served. Upgrading the module creates these
cursor fields; no data migration or version bump is needed.

Explicit negations such as "No PV required", "No TSSC required" and "No negative
vetting required" remain eligible, just like negated NV1/NV2 requirements.
