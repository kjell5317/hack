# Owner setup

You create the team's repo, hold the API keys and deploy. About 20 minutes plus the first pipeline.

On Windows, use PowerShell and type `.\hack` wherever this says `./hack`.

You need accounts at GitHub, Supabase, Hetzner Cloud, Cloudflare (with your domain added as a zone) and Langfuse, plus the LLM key from the hackathon partner.

## 1. Create the team repo

Once ever, make the baseline a template:

```sh
gh repo edit <you>/hack --template
```

For each hackathon, create the team's repo from the template and clone it:

```sh
gh repo create <you-or-org>/<project> --template <you>/hack --private --clone
cd <project>
```

No `gh` yet? On GitHub, open the baseline repo, click **Use this template → Create a new repository**, then `git clone` the new repo and `cd` into it.

## 2. Install everything

```sh
./hack setup
```

Setup installs or upgrades what's missing: Docker Desktop, Node, Python, the Supabase CLI, the GitHub CLI and `age`. It opens your browser once to sign in to GitHub and adds your SSH key to your account. If it installed Docker Desktop, start Docker once, accept its terms, and run `./hack setup` again.

## 3. Add the keys

Get your Langfuse keys: at [cloud.langfuse.com](https://cloud.langfuse.com), create a project, then go to **Settings → API Keys → Create new API keys**.

```sh
./hack env fill
```

Press Enter to skip a value. Fill in:

| Key | Value |
| --- | --- |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GOOGLE_API_KEY` | the partner's key, whichever kind it is |
| `OPENAI_BASE_URL` | only for an OpenAI-compatible partner API: its base URL |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | `pk-lf-…` and `sk-lf-…` |
| `LANGFUSE_BASE_URL` | only for the US region: `https://us.cloud.langfuse.com` |

## 4. Check that it runs

```sh
./hack dev
```

1. Open <http://localhost:5173>.
2. Sign up with any email and password.
3. Send a message in **LLM playground**. You should get a reply and a **Langfuse trace** link.

Ctrl+C stops the app.

## 5. Invite your teammates

```sh
gh api -X PUT "repos/{owner}/{repo}/collaborators/<their-github-username>"
```

Repeat for each teammate. Send them the link to [setup-teammate.md](setup-teammate.md).

## 6. Share the keys with the team

Wait until your teammates have run `./hack setup`, which puts their SSH keys on GitHub. Then:

```sh
./hack env share
git push
```

Run it again whenever someone joins late, or after you change a key.

## 7. First deploy

```sh
./hack deploy
```

The first run creates `infra/terraform.tfvars` and stops. Open that file and fill in:

| Value | Where to get it |
| --- | --- |
| `hcloud_token` | [Hetzner Console](https://console.hetzner.cloud) → your project → **Security → API tokens → Generate API token**, permission **Read & Write** |
| `cloudflare_api_token` | [dash.cloudflare.com](https://dash.cloudflare.com) → **My Profile → API Tokens → Create Token → Custom token**: permissions **Zone · DNS · Edit** and **Zone · Zone · Read**, zone resources: your zone |
| `supabase_access_token` | [supabase.com/dashboard/account/tokens](https://supabase.com/dashboard/account/tokens) → **Generate new token** |
| `supabase_organization_id` | the `<slug>` in `supabase.com/dashboard/org/<slug>` |
| `cloudflare_zone` | your domain, e.g. `example.com` |
| `subdomain` | e.g. `myteam`, so the app runs at `https://myteam.example.com` |
| `name` (optional) | a short project name, needed if another deploy already uses `hack` in your Hetzner project |

Then run it again:

```sh
./hack deploy     # type "yes" when Terraform shows its plan
gh run watch      # the first pipeline takes about 5 minutes
```

Open `https://<subdomain>.<zone>` and sign up.

## From now on

| When | Do |
| --- | --- |
| Code is merged or pushed to `main` | Nothing: CI tests it and deploys it |
| You changed a key in `.env` | `./hack env share && git push` (team), then `./hack deploy` (production) |
| Follow a deploy | `gh run watch` |
| Read production logs | `ssh root@$(terraform -chdir=infra output -raw ipv4)`, then `cd /opt/app && docker compose logs -f backend` |
| The hackathon is over | `./hack destroy`. This deletes the server, the DNS record and the Supabase project with its data. |

Keep `infra/terraform.tfvars` and `infra/terraform.tfstate` on this machine; they aren't in git, and `./hack deploy` and `./hack destroy` need them.
