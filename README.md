# Blog de disseny social · Honest

Web estàtica del blog de disseny social d'Honest. Direcció d'art Honest.
Es publica a Netlify i els articles s'editen amb **Decap CMS** a `/admin/`.

## Estructura

```
articles/        els articles (.md amb frontmatter). Els edita el CMS
img/             imatges pròpies i les que es pugen des del CMS
admin/           panell de Decap CMS (index.html + config.yml)
build.py         generador: llegeix articles/ i escriu dist/
content.py       titulars gancho i imatges (Are.na / Wikimedia) dels 32 primers articles
dev.py           servidor local amb recàrrega en viu
netlify.toml     Netlify executa `python3 build.py` i publica dist/
```

## Treballar en local

```bash
python3 dev.py          # http://localhost:4747, es recarrega sol amb cada canvi
python3 build.py        # només genera dist/
```

## Publicar

Cada `git push` a `main` fa que Netlify regeneri i publiqui el blog.
Des del CMS, en desar un article també es fa un commit i Netlify el publica sol.

## Articles nous (des del CMS)

- Títol amb el format «Concepte: formulació».
- Camps opcionals: **titular** (el titular gancho), **subtítol**, **imatge destacada**.
- El text, amb tres seccions `##`. Les imatges que s'hi posen es guarden a `img/`.
- Els articles nous es numeren sols després dels existents, per data.

## Configurar el CMS a Netlify (una sola vegada)

1. A GitHub: *Settings → Developer settings → OAuth Apps → New OAuth App*
   - Homepage URL: l'adreça del blog a Netlify
   - Authorization callback URL: `https://api.netlify.com/auth/done`
2. A Netlify: *Site configuration → Access & security → OAuth → Install provider* → GitHub,
   amb el *Client ID* i el *Client secret* de l'app de GitHub.
3. Entra a `https://<el-teu-blog>/admin/` i inicia sessió amb GitHub.
