## What This Repo Is

[GarudaSeva/zanu-coliving-website](https://github.com/GarudaSeva/zanu-coliving-website) is the marketing site for **Zanu Sunidhi Guest Inn**, a co-living PG in Gachibowli, Hyderabad. It's a single-page brochure site: hero, rooms, facilities, gallery, location, and contact sections, all wrapped in a modern React stack. The business sells affordable rooms starting at ₹599, with A/C and non-A/C options, furnished interiors, 24/7 security, Wi-Fi, and housekeeping.

What makes this repo interesting isn't the business itself — it's how the site was built. The project was generated with **Lovable**, an AI app builder, and it shows. The stack is current, the structure is clean, and the SEO groundwork is solid. But there are also a few rough edges that a developer should fix before this goes to production.

## The Stack at a Glance

- **Build tool**: Vite 5
- **Language**: TypeScript 5.8 (with relaxed strictness)
- **Framework**: React 18.3
- **Styling**: Tailwind CSS 3.4 + shadcn/ui components
- **Routing**: react-router-dom 6.30
- **Forms**: react-hook-form + zod
- **Data fetching**: @tanstack/react-query + axios
- **Deployment**: Vercel (with SPA rewrites)

The dependency list is heavy — about 60 packages — but that's typical of a shadcn/ui project. Nearly every Radix UI primitive is included, even if only a handful are used. It's the price of convenience when you scaffold with a component library.

## What the Site Does Well

### SEO Is Thought Out

The `index.html` file is the standout. It includes a descriptive title, meta description, keywords, Open Graph tags, and Twitter card tags, all targeting local search terms like "PG in Gachibowli" and "Co-living Hyderabad." The `robots.txt` explicitly allows Googlebot, Bingbot, Twitterbot, and Facebook's crawler. For a small local business, this is more than most competitors bother with.

### Clean Component Structure

The site is organized into logical components: `Hero`, `Rooms`, `Facilities`, `Gallery`, `Location`, `Contact`, `Navbar`, and `Footer`. Each is a self-contained file under `src/components/`. The `Index` page composes them in order. This makes the code easy to navigate and modify — you know exactly where to change room pricing or add a new facility.

### Sensible Tooling

- Path alias `@/*` → `./src/*` is configured in both `tsconfig` and `vite.config.ts`, so imports stay short and consistent.
- The Vercel config uses a catch-all rewrite to `/`, which is the correct fix for client-side routing on a single-page app. Refresh a route and it won't 404.
- The dev server runs on port 8080 with host `::`, which works well in containerized environments like Lovable's preview.

## Where It Could Improve

### Broken Social Media Image Paths

This is the most obvious bug. In `index.html`, both `og:image` and `twitter:image` point to `zenu-co-living\public\favicon.png` — a Windows-style local path. When social platforms try to fetch that URL, they'll hit a 404. The fix is simple: use an absolute URL to the deployed site, e.g. `https://yourdomain.com/favicon.png`. Until then, shared links will lack a preview image.

### No Visible Form Backend

The `Contact` component uses `react-hook-form` and `zod` for validation, and `axios` is in the dependencies, which suggests the form posts to an API. But no endpoint is visible in the repo. That could mean the form is wired to a serverless function that isn't included, or it's still a stub. Either way, a developer should verify the form actually sends data somewhere — otherwise leads are silently lost.

### Relaxed TypeScript Strictness

The `tsconfig` files set `strict: false`, `noImplicitAny: false`, and `noUnusedLocals: false`. This is common in Lovable-generated projects to reduce friction during AI-assisted development. It speeds things up, but it also means type errors that could catch bugs at compile time are ignored. For a small marketing site, this is acceptable. For anything more complex, I'd tighten it.

### Unused Dependencies

The package list includes `recharts`, `react-day-picker`, `input-otp`, `vaul`, and a dozen Radix primitives that likely aren't used. This bloats the bundle and increases the attack surface. Running `npm uninstall` on unused packages would shrink the final build and make the repo easier to maintain.

## What This Repo Demonstrates

This project is a perfect example of how fast you can ship a production-ready marketing site with modern tooling. Lovable + shadcn/ui + Vercel means a non-technical business owner can go from idea to deployed site in hours. The SEO meta tags, the clean component split, and the SPA routing all show that the generated code is far from throwaway.

But it also shows why a human review matters before launch. Broken image paths, an unverified form backend, and a pile of unused dependencies are exactly the kind of issues that slip through when AI generates code and nobody double-checks the details.

If you're building a similar site — whether for a co-living space or any local business — take the good parts from this repo: the SEO groundwork, the component structure, the deployment setup. Then do the cleanup: fix the meta tags, wire up the form, and trim the dependencies. The result will be a fast, reliable site that actually converts visitors into customers.