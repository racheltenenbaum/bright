const EFFECTIVE_DATE = "August 4, 2026";
const CONTACT_EMAIL = "bright.sunshine.contact@gmail.com";

function Section({ title, children }) {
  return (
    <div style={{ marginBottom: "26px" }}>
      <h3 style={{ fontSize: "1.05em", margin: "0 0 8px" }}>{title}</h3>
      <div style={{ fontSize: "0.9em", lineHeight: 1.7, color: "var(--color-text)" }}>
        {children}
      </div>
    </div>
  );
}

export default function PrivacyPolicyPage() {
  return (
    <div className="page-container">
      <div className="content-inner" style={{ maxWidth: "720px", margin: "0 auto", padding: "32px 20px 60px" }}>
        <h2 style={{ marginBottom: "4px" }}>Privacy Policy</h2>
        <p style={{ fontSize: "0.85em", color: "var(--color-subtext)", marginTop: 0 }}>
          Effective {EFFECTIVE_DATE}
        </p>

        <Section title="Who we are">
          <p>
            bright ("bright", "we", "us") is a walking-route app that helps you find sunny or
            shaded paths. This policy explains what information bright collects, why, and the
            choices and rights you have over it. bright is operated by Rachel Tenenbaum. You can
            reach us at <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> with any privacy
            question or request.
          </p>
        </Section>

        <Section title="Information we collect">
          <p><strong>Account information.</strong> When you register, we collect your first name,
            email address, and password. Your password is never stored in plain text — it's
            hashed with bcrypt before being saved.</p>
          <p><strong>Preferences.</strong> Your sun/shade mode, maximum detour tolerance, and map
            display settings, so the app remembers how you like it.</p>
          <p><strong>Routes and spots you save.</strong> If you save a route or a spot, we store
            its name, description, start/end coordinates or address, and (for spots) the
            location, category icon, and any Google Place ID associated with it.</p>
          <p><strong>Location.</strong> With your permission, bright uses your device's location
            in the foreground to show your position on the map, center searches near you, and
            calculate sunny/shady routes. This location is used live and is only stored if you
            explicitly save it as part of a route or spot. bright does not track or collect your
            location in the background when the app isn't open.</p>
          <p><strong>Shared links.</strong> If you generate a share link for a route or spot,
            anyone with that link can view the shared route or spot details without needing an
            account or logging in.</p>
        </Section>

        <Section title="How we use your information">
          <p>We use the information above solely to operate and improve bright: authenticating
            you, calculating and displaying sun/shade routes, remembering your saved places and
            preferences, and enabling link-sharing when you choose to use it. We do not sell your
            personal information, and we do not use it for advertising or profiling.</p>
        </Section>

        <Section title="Third parties we work with">
          <p>bright relies on a small number of service providers to function:</p>
          <ul style={{ margin: "8px 0", paddingLeft: "20px" }}>
            <li><strong>Google Maps Platform</strong> — powers the map display, address
              autocomplete, and geocoding. Search text and location data you enter may be sent to
              Google as part of these requests, subject to{" "}
              <a href="https://policies.google.com/privacy" target="_blank" rel="noreferrer">
                Google's Privacy Policy
              </a>.</li>
            <li><strong>OpenStreetMap / Overpass API</strong> — provides building and terrain data
              used to calculate shadows. Only geographic coordinates are sent; no personal or
              account information is included.</li>
            <li><strong>Railway</strong> — hosts our backend application and database. Railway
              acts as our infrastructure provider and processes data solely on our behalf.</li>
          </ul>
        </Section>

        <Section title="Data storage and security">
          <p>Your account and app data are stored in a database hosted on Railway. Access tokens
            issued when you log in are stored locally on your device to keep you signed in, and
            are removed when you log out. We use industry-standard practices (password hashing,
            rate limiting on authentication endpoints, HTTPS in transit) to protect your data, but
            no system can guarantee absolute security.</p>
        </Section>

        <Section title="Data retention">
          <p>We retain your account information and saved routes/spots for as long as your
            account exists. You can delete individual routes or spots at any time, or permanently
            delete your entire account — including all associated routes and spots — from the
            Danger Zone section of My Account. Account deletion is immediate and irreversible.</p>
        </Section>

        <Section title="Your rights (GDPR, UK GDPR, and similar laws)">
          <p>If you're located in the EU, UK, or other regions with similar protections, you have
            the right to:</p>
          <ul style={{ margin: "8px 0", paddingLeft: "20px" }}>
            <li>Access the personal data we hold about you</li>
            <li>Correct inaccurate data (via My Account, or by contacting us)</li>
            <li>Erase your data (delete your account at any time, or request erasure by email)</li>
            <li>Receive a copy of your data in a portable format</li>
            <li>Object to or restrict certain processing</li>
            <li>Lodge a complaint with your local data protection authority</li>
          </ul>
          <p>Because bright is hosted on infrastructure located in the United States, using the
            app means your data is transferred to and processed in the US.</p>
        </Section>

        <Section title="California and other US state privacy rights">
          <p>If you're a California resident (or a resident of another state with a comprehensive
            privacy law), you have similar rights to know, access, and delete your personal
            information. bright does not sell or share personal information for cross-context
            behavioral advertising.</p>
        </Section>

        <Section title="Children's privacy">
          <p>bright is not directed at children, and we do not knowingly collect personal
            information from anyone under 16. If you believe a child has provided us with
            personal information, contact us and we will delete it.</p>
        </Section>

        <Section title="Changes to this policy">
          <p>If we make material changes to this policy, we'll update the effective date above
            and, where appropriate, notify you in the app.</p>
        </Section>

        <Section title="Contact us">
          <p>Questions, requests to access/delete your data, or anything else — email{" "}
            <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.</p>
        </Section>
      </div>
    </div>
  );
}
