import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { createClient } from "@supabase/supabase-js";
import { Button, Input, Card, CardContent } from "@/components/ui";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
);

export default function Dashboard() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState({
    firstName: "",
    lastName: "",
    telegramHandle: "",
    linkedinURL: "",
  });
  const [company, setCompany] = useState({
    name: "",
    website: "",
    twitterHandle: "",
    telegramChannel: "",
    linkedinURL: "",
    category: "",
  });
  const [existingCompanies, setExistingCompanies] = useState([]);
  const [selectedCompanyIds, setSelectedCompanyIds] = useState([]);

  const [searchParams] = useSearchParams();
  const telegramUserId = searchParams.get("tg_id");

  useEffect(() => {
    async function fetchData() {
      if (!telegramUserId) return;
      
      // Fetch existing companies
      const { data: companies } = await supabase.from("companies").select("id, name");
      setExistingCompanies(companies || []);
      
      // Fetch user profile
      const { data: userProfile } = await supabase
        .from("users")
        .select("*")
        .eq("telegram_id", telegramUserId)
        .single();

      if (userProfile) {
        setProfile(userProfile);
        
        // Fetch user-company relations
        const { data: relations } = await supabase
          .from("user_company_relations")
          .select("company_id")
          .eq("user_id", userProfile.id);
        setSelectedCompanyIds(relations.map(r => r.company_id));
      }
      setLoading(false);
    }
    fetchData();
  }, [telegramUserId]);

  async function handleSave() {
    setLoading(true);
    let companyIds = [...selectedCompanyIds];

    // If a new company is being added
    if (!selectedCompanyIds.length) {
      const { data, error } = await supabase.from("companies").insert([{ ...company }]).select("id").single();
      if (data) companyIds.push(data.id);
    }

    // Upsert user profile
    const { data: userData } = await supabase.from("users").upsert({
      telegram_id: telegramUserId,
      ...profile,
    }).select("id").single();

    if (userData) {
      // Link user to selected companies
      await supabase.from("user_company_relations").delete().eq("user_id", userData.id);
      await supabase.from("user_company_relations").insert(
        companyIds.map(companyId => ({ user_id: userData.id, company_id: companyId, role: "Member" }))
      );
    }

    setLoading(false);
  }

  async function handleTelegramLogin() {
    window.location.href = `https://oauth.telegram.org/auth?bot_id=${process.env.NEXT_PUBLIC_TELEGRAM_BOT_ID}&origin=${window.location.origin}&return_to=${window.location.href}`;
  }

  return (
    <div className="flex flex-col items-center p-6">
      <h1 className="text-xl font-bold">Collab Room Dashboard</h1>
      {!telegramUserId ? (
        <Button className="mt-4" onClick={handleTelegramLogin}>
          Sign in with Telegram
        </Button>
      ) : (
        <Card className="w-full max-w-lg mt-4">
          <CardContent>
            <Input
              label="First Name"
              value={profile.firstName}
              onChange={(e) => setProfile({ ...profile, firstName: e.target.value })}
            />
            <Input
              label="Last Name"
              value={profile.lastName}
              onChange={(e) => setProfile({ ...profile, lastName: e.target.value })}
            />
            <Input
              label="Telegram Handle"
              value={profile.telegramHandle}
              onChange={(e) => setProfile({ ...profile, telegramHandle: e.target.value })}
            />
            <Input
              label="LinkedIn URL"
              value={profile.linkedinURL}
              onChange={(e) => setProfile({ ...profile, linkedinURL: e.target.value })}
            />
            
            <h2 className="mt-4 font-bold">Company Details</h2>
            <select
              className="w-full p-2 border rounded"
              multiple
              value={selectedCompanyIds}
              onChange={(e) =>
                setSelectedCompanyIds(
                  [...e.target.selectedOptions].map(option => option.value)
                )
              }
            >
              {existingCompanies.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            
            <h3 className="mt-4">Or add a new company</h3>
            <Input
              label="Company Name"
              value={company.name}
              onChange={(e) => setCompany({ ...company, name: e.target.value })}
            />
            <Input
              label="Company Website"
              value={company.website}
              onChange={(e) => setCompany({ ...company, website: e.target.value })}
            />
            <Input
              label="Twitter Handle"
              value={company.twitterHandle}
              onChange={(e) => setCompany({ ...company, twitterHandle: e.target.value })}
            />
            <Input
              label="Telegram Announcement Channel"
              value={company.telegramChannel}
              onChange={(e) => setCompany({ ...company, telegramChannel: e.target.value })}
            />
            <Input
              label="Company LinkedIn URL"
              value={company.linkedinURL}
              onChange={(e) => setCompany({ ...company, linkedinURL: e.target.value })}
            />
            <Input
              label="Category"
              value={company.category}
              onChange={(e) => setCompany({ ...company, category: e.target.value })}
            />

            <Button className="mt-4" onClick={handleSave} disabled={loading}>
              {loading ? "Saving..." : "Save Profile"}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
