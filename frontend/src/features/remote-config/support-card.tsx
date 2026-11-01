import { FileText, LifeBuoy, Mail, MessageCircle, ShieldCheck } from 'lucide-react'

import { useRemoteConfig } from './api'

function whatsappLink(phone: string) {
  return `https://wa.me/${phone.replace(/\D/g, '')}`
}

/** Configuración → Acerca de: support contacts and legal links from the vendor's remote config. */
export function SupportCard() {
  const { data } = useRemoteConfig()
  const s = data?.support
  if (!s || !(s.email || s.whatsapp || s.terms_url || s.privacy_url)) return null
  const links = [
    s.email && { href: `mailto:${s.email}`, label: s.email, icon: Mail },
    s.whatsapp && { href: whatsappLink(s.whatsapp), label: `WhatsApp ${s.whatsapp}`, icon: MessageCircle },
    s.terms_url && { href: s.terms_url, label: 'Términos y condiciones', icon: FileText },
    s.privacy_url && { href: s.privacy_url, label: 'Política de privacidad', icon: ShieldCheck },
  ].filter((l): l is { href: string; label: string; icon: typeof Mail } => !!l)
  return (
    <div className="flex items-start gap-3 rounded-xl border p-4" data-testid="support-card">
      <LifeBuoy className="mt-0.5 size-5 text-muted-foreground" />
      <div className="grid gap-1.5 text-sm">
        <p className="font-medium">Ayuda y soporte</p>
        {links.map((l) => (
          <a
            key={l.href}
            href={l.href}
            target="_blank"
            rel="noopener noreferrer"
            className="flex min-h-8 items-center gap-2 text-primary hover:underline"
          >
            <l.icon className="size-4" /> {l.label}
          </a>
        ))}
      </div>
    </div>
  )
}
