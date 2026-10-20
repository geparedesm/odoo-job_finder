# Job Finder

Job Finder keeps a structured professional profile in Odoo, imports it from a PDF CV, prints it as a complete CV,
and publishes it as a bilingual portfolio website.

## Structured profile

A profile (`job.profile`) holds the identity and contact details (name, headline, photo, location, email, phone,
LinkedIn, GitHub, website, summary) and these records, each with a sequence and a **Show on portfolio** flag:

| Model | Content |
| --- | --- |
| `job_finder.experience` | Roles: professional experience or academic research, with company, location, start and end (or *I currently work here*, or *Show years only*), employment type, description, and highlights (one per line). |
| `job_finder.project` | Projects, usually inside a role: subtitle (client or short description), description, technologies, link, and **Featured** (listed in the portfolio's Selected work). |
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
`/` shows it (and `/es/` in Spanish). It follows the design in `ui/portfolio.pen` (desktop 1440 and mobile 390):
hero with photo, Selected work, Experience, Research and academic projects, Skills, Education, Training and
credentials, Languages, Leadership and volunteering, and Contact. Sections and navigation links appear only when
they have entries shown on the portfolio.

### Publishing

1. Complete the profile (or import the CV) and add a photo.
2. As an administrator, switch on **Publish as portfolio** next to the headline, and save.
3. Optionally, in the **Portfolio** tab: show the phone (hidden by default; it always appears in the complete CV)
   and adjust the search engine and sharing title, description and image (they default to the name and headline,
   the summary, and the photo).

Only one profile can be published at a time.

### Languages and domain

Languages are the website's languages (Website › Configuration › Settings): the EN / ES links switch the whole page,
including the fixed texts from `i18n/es.po` and the translated profile texts. The domain is the website's
**Website Domain** setting; DNS, TLS and the reverse proxy are configured outside this module.

### Portfolio and CV access

The public portfolio does not show CV download links. `/portfolio/cv` remains available to signed-in internal users;
anonymous visitors are sent to log in first, and portal and other external accounts get 403 Forbidden. Only the
published profile's photo is public, at `/portfolio/photo`.

For an isolated visual preview, run `.hermes/preview-seed.py` in an Odoo shell connected to a disposable preview
database, setting `JOB_FINDER_PREVIEW_DATABASE` to that database's exact name. The hook creates or updates a
dedicated synthetic profile with a deliberately long email address. To preview the no-email state, clear the email
on the synthetic `Portfolio Preview` profile in that same isolated database.

## Complete CV

**Download complete CV** in the form header (or Print › Complete CV) generates the PDF from the saved records:
roles with highlights and projects, academic research, skills by area, education, trainings, volunteering and
languages. Entries hidden from the portfolio still appear in the complete CV. Profile access rules apply to
downloads.

## Upgrading from 19.0.1.0.0

The migration to 19.0.1.1.0 builds the records from the text stored by earlier versions (only for profiles that
have no records yet), sets `/portfolio` as the website homepage when none is set, and removes the former
`job_finder.portfolio_hosts` parameter.
