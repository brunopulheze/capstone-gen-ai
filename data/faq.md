# NexaLab — FAQ

## Pricing & Budget

**How much does a project cost?**
Every project is different, so we scope each one individually before quoting. Pricing depends on the scope, timeline, and complexity. We're transparent throughout — no surprise invoices. To get a quote, book a discovery call or use the "Scope a Project" chat mode.

**Do you work with fixed budgets?**
Yes. If you share your budget upfront, we'll scope the project to fit it and be honest if it's not feasible rather than overpromising.

**What are typical price ranges?**
- Landing page / marketing site: from ~$1,500–$4,000
- MVP web app: from ~$5,000–$15,000
- AI chatbot / RAG system: from ~$3,000–$10,000
- Data dashboard: from ~$2,000–$7,000
These are rough guides — every project gets a personalised quote.

---

## Timeline & Process

**How long does a project take?**
A landing page: 1–2 weeks. An MVP: 4–8 weeks. A full SaaS product: 3–6 months. Timeline depends on complexity and how quickly decisions get made on your side.

**What does the process look like?**
1. **Discovery call** — understand goals, constraints, existing systems
2. **Proposal & scope** — detailed spec with timeline and fixed quote
3. **Design phase** — wireframes and prototypes for feedback before any code is written
4. **Development sprints** — weekly demos so you can see progress
5. **QA & handoff** — testing, documentation, and deployment
6. **Post-launch support** — 30-day bug fixing included

**Do you do ongoing retainer work?**
Yes. Some clients keep us on a monthly retainer for feature development, analytics reporting, or chatbot maintenance.

---

## Technical Questions

**What tech stack do you use most?**
We default to Next.js + TypeScript on the frontend, FastAPI or Node.js on the backend, PostgreSQL for relational data, and Vercel/Railway for deployment. We adapt to your existing stack when needed.

**Can you work with an existing codebase?**
Yes — we've joined projects at every stage. We always do a brief audit first to understand the code quality and flag any risks.

**Do you handle deployment and hosting?**
Yes. We set up CI/CD pipelines and hosting (Vercel, Railway, Render, AWS). We can also hand off to your infrastructure team with full documentation.

**What AI models do you use?**
Primarily Groq (Llama 3, Deepseek), OpenAI (GPT-4o, embeddings), and Anthropic (Claude). We choose based on cost, speed, and capability requirements per project.

---

## Working Together

**How do we communicate?**
Primarily async via Notion or Linear for project tracking, with weekly video syncs. We respond to messages within 24 hours on business days.

**Do you sign NDAs?**
Yes, we're happy to sign NDAs before discussing sensitive project details.

**Can I see more portfolio examples?**
The portfolio currently showcases Orbitly and GreenRoots. More case studies are in progress — reach out for relevant samples based on your industry or project type.

**How do I get started?**
Book a free 30-minute discovery call using the booking link: https://calendly.com/alexrivera/discovery-call
Or use the chat widget to describe your project briefly — we'll follow up within 24 hours.

---

## NexaLab Chatbot

**What is NexaLab Assistant?**
NexaLab Assistant is the virtual assistant built into this portfolio. It can answer questions about the studio's services and past projects, help you scope a new project, perform quick UX/accessibility audits on screenshots or URLs, analyse data files (CSV/Excel), and book a discovery call — all from a single chat interface.

**What can I ask NexaLab Assistant?**
Anything about NexaLab: services, projects, pricing guidance, tech stack, process, and timelines. You can also activate specific service modes:
- 🎨 **UX Audit** — upload a screenshot or paste a URL to get instant UX and accessibility feedback
- 📊 **Data Insights** — upload a CSV or Excel file for automated statistical analysis and visualisations
- 💼 **Scope a Project** — guided Q&A to define your project and get a scoping summary
- 📅 **Book a Call** — quick path to scheduling a discovery call via Calendly

**How does the data analysis feature work?**
Upload a CSV or Excel file (up to 5 MB) in Data Insights mode. The backend parses it with pandas, builds column profiles, computes statistics (distributions, correlations, missing values, outliers) and generates a visual insights panel with charts, a correlation heatmap, and an AI-written narrative summary. You can then ask follow-up questions about your data in plain English.

**How does the UX Audit feature work?**
Paste a URL or upload a screenshot of any web page. The AI uses a vision model to evaluate the page against UX best practices and WCAG accessibility guidelines, then returns structured feedback covering visual hierarchy, contrast, spacing, navigation, and mobile responsiveness. After the audit you can ask follow-up questions or request a professional audit scope.

**Is my data private?**
Files you upload are processed in memory for the duration of your session and never stored on disk or in any database. Conversations are not logged by the studio. Standard API provider data policies (Groq) apply to the text sent to the language model.

**What AI models power BrixoAI?**
The chat is powered by Llama 3.3 70B via Groq. Studio knowledge is retrieved from a local vector database (ChromaDB) using sentence-transformer embeddings — no external vector DB API calls. Vision analysis uses Llama 4 Scout (Groq multimodal).
