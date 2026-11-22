# Teammate setup

You need a GitHub account and an invite to the team's repo. Allow about 15 minutes; most of it is downloads.

On Windows, use PowerShell and type `.\hack` wherever this says `./hack`.

## 1. Accept the invite

Open the invitation email from GitHub, or go to `https://github.com/<owner>/<repo>/invitations`, and accept.

## 2. Get the code

If `git` isn't installed:

- **macOS:** `xcode-select --install`
- **Windows:** `winget install --id Git.Git -e`, then open a new PowerShell

```sh
git clone https://github.com/<owner>/<repo>.git
cd <repo>
```

## 3. Install everything

```sh
./hack setup
```

- Setup installs or upgrades what's missing: Docker Desktop, Node, Python, the Supabase CLI, the GitHub CLI and `age`. It may ask for your password or for admin approval.
- It opens your browser once to sign in to GitHub, and adds your SSH key to your GitHub account (it creates a key if you have none).
- If it installed Docker Desktop: start Docker once, accept its terms, and run `./hack setup` again.

When it's done, tell the owner you've finished setup.

## 4. Get the team's keys

After the owner has run `./hack env share`:

```sh
git pull
./hack env pull
```

If it says your SSH key can't decrypt `.env.age`, the share happened before your setup. Ask the owner to run `./hack env share` once more, then repeat this step.

## 5. Run the app

```sh
./hack dev
```

1. Open <http://localhost:5173>.
2. Sign up with any email and password.
3. Ctrl+C stops the app.

## Day to day

```sh
git switch -c my-feature        # work on a branch
./hack dev                      # run the app while you work
./hack check                    # before pushing: lint + all tests
git push -u origin my-feature
gh pr create --fill             # merging the PR into main deploys it
```

| If | Run |
| --- | --- |
| Something doesn't start | `./hack doctor` |
| The owner changed a key | `git pull && ./hack env pull` |
| You need a clean local database | `./hack db reset` |
| You're done for the day | `./hack stop` |
