# Job Finder

Uploaded PDF CVs populate professional profile details. The parser recognizes
compound headings such as Technical Skills and Professional Profile, and headings
with trailing qualifiers such as Professional Experience - Software Development.
Repeated sections accumulate in document order, including separate experience and
academic project blocks. Leadership and volunteering, academic research and
projects, and training and credentials populate the `volunteering`, `projects`,
and `trainings` profile fields. References stop section content collection.
Location is extracted from delimited contact lines. Repeated name/subtitle page
headers and name/page-count footers are excluded from section content.
Spoken languages labeled `Languages spoken` or under `Language`/`Languages` populate `languages`, while
programming languages remain in skills. LinkedIn populates its dedicated field. Personal website and GitHub links also populate
their dedicated contact fields, which appear in the form and downloaded CV.
Training and Credentials is retained in full in `trainings`.
Only explicitly authorized profile fields are saved. Empty parsed fields preserve
existing profile values.

Regression fixtures include the complete six-page reference PDF, its extracted
text and exact expected values for every field. Odoo tests parse and save the real
PDF without mocking the parser, then check preservation after empty/invalid input.

## Public Portfolio Page

A published job profile is available as a public, bilingual portfolio page at `/` for configured hosts
(default: `gp-developer.com` and `www.gp-developer.com`). The portfolio is not available via other hosts
or paths; those keep Odoo's standard `/` behavior.

### Publishing a Portfolio

To publish your profile as the portfolio:
1. Complete your profile (or upload and analyze your CV).
2. In Job Finder › My profile, check **Publish as portfolio** (admin-only field).
3. Save the profile.

Only one profile can be published at a time. Publishing another profile raises a validation error; unpublish the first one first.

### Portfolio Content and Format

The portfolio renders:
- **Name and headline** in the hero section (from `full_name` and `headline`).
- **Skills** as individual items, split by newlines, commas, or bullets.
- **Projects** as cards, split by blank lines (first line is the title, rest is description).
- **Experience and Education** as a timeline (first line is title, second is date/location, rest is details).
- **Summary, Languages, Trainings, and Volunteering** as paragraphs or lists.
- **Contact** (email, LinkedIn, GitHub, website) with links.

**Formatting tips**: Use blank lines to separate project and experience entries. Each entry can have multiple lines for details.

### Language Selection

The portfolio includes an **EN | ES** selector (top right). Clicking a language:
- Switches fixed page text to that language (if activated in Odoo settings).
- Saves the choice in a cookie (`job_finder_lang`, valid 1 year).
- Reloading the page remembers your language choice.

Invalid or unavailable languages fall back to English.

### Download CV

Anonymous visitors see a **Login** button. After logging in, the button becomes **Open app** and a **Download CV** button appears.
Clicking **Download CV** downloads the complete PDF CV (includes email, phone, and location). Only logged-in users can download.

### Configuring Hosts

The system parameter `job_finder.portfolio_hosts` controls which hosts serve the portfolio (comma-separated list). Change it in Settings › Technical › System Parameters to add or remove hosts. The default is `gp-developer.com,www.gp-developer.com`.

**Note for reverse proxies**: The reverse proxy must forward the original `Host` header and enable Odoo's `proxy_mode` so that `X-Forwarded-Host` is recognized. DNS and TLS for the portfolio domain are configured outside this module.

## Profile Form

The guided form starts with contact details, followed by PDF upload instructions and the portfolio publishing checkbox (admin-only).
The header provides the analysis and download actions.
Upload your CV, then click **Analyze CV** (**Analizar CV** in Spanish). Review and
edit the extracted content in the tabs: summary, skills, experience, education,
volunteering, projects, trainings, and languages.
Each tab includes a placeholder suggesting which details to include.
The parser behavior and three dedicated fields described above shipped in T-56-1;
this form layout adds guidance and makes those fields available for review.

## Download the complete CV

Save your profile edits, then click **Download complete CV** in the form header
(**Descargar CV completo** in Spanish), or select **Complete CV** from the Print menu.
The PDF includes your current name, headline, contact data, summary, skills,
experience, education, volunteering, projects, trainings, and languages. Multiline
entries retain their line breaks; empty sections are omitted. You can download a manually completed profile without uploading a PDF.

Downloads are generated afresh from saved profile values, including additions made
after parsing. The original uploaded file and parser diagnostics remain available in
Odoo; they are not appended to the professional CV. Existing profile access rules also
apply to downloads, so users can only download profiles they are allowed to read.
