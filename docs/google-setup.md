# Google setup

## 1. Cloud project and APIs

In the Google Cloud Console, enable:

- My Business Account Management API
- My Business Business Information API
- My Business Notifications API, Verifications API, Place Actions API, Lodging API
- Google My Business API (only visible after access is approved, see step 3)

## 2. OAuth consent and client

In **Google Auth Platform**:

1. **Branding:** app name, support and contact email.
2. **Audience:** External, then **Publish app** so the status is **In production**. In Testing mode refresh tokens expire after 7 days.
3. **Data Access:** add the scope `https://www.googleapis.com/auth/business.manage`.
4. **Clients:** Web application with these redirect URIs:
   - `http://localhost:8000/oauth/callback`
   - `https://reviews.lab.upintown.dev/oauth/callback`

Copy the client ID and secret into `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`. Never commit the downloaded JSON file.

## 3. API access request

Business Profile APIs require approval. Submit the GBP API contact form and choose **Application for Basic API Access**, using:

- the project number (numeric, on the project dashboard)
- an email that is owner or manager on a profile verified for more than 60 days, with a website

Check the quota of the Account Management API in the Cloud Console: **0 QPM** means pending, **300 QPM** means approved.

## 4. Client profiles

Each client adds the agency Google account as **Manager** on their Business Profile. The app finds new locations on the next cycle and emails a link to configure them.

## 5. Connect the app

Once approved, set `GBP_MODE=live`, open the dashboard and click **Connect Google**. Log in with the agency account. If Google shows an unverified app warning, choose **Advanced** and continue. The refresh token is stored encrypted and is reused until revoked.
