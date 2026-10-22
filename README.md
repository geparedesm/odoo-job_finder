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

**Download CV** opens `/portfolio/cv`; for visitors who are not signed in it shows a lock. Anonymous visitors get a
sign-in page (Odoo's login form, returning to the download) with a link to request the CV by email; internal users
download the complete PDF; portal and other external accounts get a 403 page that suggests requesting it by email.
Only the published profile's photo is public, at `/portfolio/photo`.

## Complete CV

**Download complete CV** in the form header (or Print › Complete CV) generates the PDF from the saved records:
roles with highlights and projects, academic research, skills by area, education, trainings, volunteering and
languages. Entries hidden from the portfolio still appear in the complete CV. Profile access rules apply to
downloads.

## Upgrading to 19.0.1.2.0

A CV import marks professional roles without projects (production, hospitality…) as secondary. The migration to
19.0.1.2.0 applies the same rule to the existing roles; change **Show as secondary** on any role afterwards.

## Upgrading from 19.0.1.0.0

The migration to 19.0.1.1.0 builds the records from the text stored by earlier versions (only for profiles that
have no records yet), sets `/portfolio` as the website homepage when none is set, and removes the former
`job_finder.portfolio_hosts` parameter.
