# Publish the project to GitHub

1. Create a new **public** GitHub repository named `brandproof-desk` (or your preferred name). Do not initialise it with a README because this source bundle already contains one.
2. Extract the ZIP into a folder named `brandproof-desk`.
3. Open PowerShell in that folder and run:

```powershell
git init
git add .
git status
git commit -m "Build BrandProof Desk Round 2 MVP"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/brandproof-desk.git
git push -u origin main
```

4. Replace `YOUR_USERNAME` with your actual GitHub username.
5. Confirm `.env` is not tracked. Only `.env.example` belongs in the repository. Never commit an Adaption API key, MongoDB URI, password or token.
6. After you make real changes, commit them with meaningful messages. Do not create backdated commits or claim that generated code was manually written line by line.

For a portfolio repo, add the working deployment URL to the GitHub repository's About section and README after deployment. Include screenshots or a short demo video made from your actual running build.
