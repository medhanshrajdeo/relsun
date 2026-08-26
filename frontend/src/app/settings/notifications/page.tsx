import { Bell } from "lucide-react";
import { SettingsHeader, SettingsPage, SettingsSection, StubSection } from "@/components/settings/primitives";

export default function NotificationsSettingsPage() {
  return (
    <>
      <SettingsHeader icon={Bell} title="Notifications" description="Control what Relsun notifies you about." />
      <SettingsPage>
        <SettingsSection>
          <StubSection label="Notification preferences" />
        </SettingsSection>
      </SettingsPage>
    </>
  );
}
