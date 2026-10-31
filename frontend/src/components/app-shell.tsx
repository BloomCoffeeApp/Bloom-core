import { useQuery } from '@tanstack/react-query'
import { Bell, CircleHelp, GraduationCap, Lock, LogOut, Monitor, Moon, Search, Sun } from 'lucide-react'
import { Fragment, useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router'

import { CommandPalette } from '@/components/command-palette'
import { useDesktop, useTitleBarDrag, WindowControls } from '@/components/window-controls'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
  useSidebar,
} from '@/components/ui/sidebar'
import { hasFeature, useLicense } from '@/features/license/api'
import { LicenseBanner, ProBadge } from '@/features/license/pro-gate'
import { useTour } from '@/features/tutorial/tour'
import { useIdleLock } from '@/hooks/use-idle-lock'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { ROLE_LABEL } from '@/lib/format'
import { NAV, NAV_GROUPS } from '@/lib/nav'
import { useTheme } from '@/lib/theme'
import { cn } from '@/lib/utils'
import { Logo } from '@/components/logo'
import { BRAND } from '@/lib/brand'

export const AVATAR_COLORS: Record<string, string> = {
  amber: 'bg-amber-500/20 text-amber-700 dark:text-amber-300',
  sky: 'bg-sky-500/20 text-sky-700 dark:text-sky-300',
  emerald: 'bg-emerald-500/20 text-emerald-700 dark:text-emerald-300',
  violet: 'bg-violet-500/20 text-violet-700 dark:text-violet-300',
  rose: 'bg-rose-500/20 text-rose-700 dark:text-rose-300',
  orange: 'bg-orange-500/20 text-orange-700 dark:text-orange-300',
}

export const initials = (name: string) =>
  name
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('')

interface AlertSummary {
  open: number
  critical: number
}

/** On phones the sidebar is a sheet: close it once a link (or the palette) navigates. */
function CloseMobileSidebarOnNavigate() {
  const { pathname } = useLocation()
  const { isMobile, setOpenMobile } = useSidebar()
  useEffect(() => {
    if (isMobile) setOpenMobile(false)
  }, [pathname, isMobile, setOpenMobile])
  return null
}

export function AppShell() {
  const { user, can, logout } = useAuth()
  const { theme, setTheme } = useTheme()
  const [paletteOpen, setPaletteOpen] = useState(false)
  const tour = useTour()
  const license = useLicense()
  const desktop = useDesktop()
  const drag = useTitleBarDrag()
  const marginDrag = useTitleBarDrag({ selfOnly: true })
  const location = useLocation()
  const navigate = useNavigate()
  useIdleLock()

  const { data: alertSummary } = useQuery({
    queryKey: ['alerts', 'summary'],
    queryFn: () => api.get<AlertSummary>('/alerts/summary'),
    refetchInterval: 60_000,
    retry: false,
  })

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen((o) => !o)
      }
      if (e.key === 'F1' && can('cajero', 'encargado')) {
        e.preventDefault()
        navigate('/pos')
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [can, navigate])

  if (!user) return null
  const items = NAV.filter((n) => n.roles.length === 0 || can(...n.roles))
  const groups = Object.entries(NAV_GROUPS)
    .map(([key, label]) => ({ key, label, items: items.filter((i) => i.group === key) }))
    .filter((g) => g.items.length)
  const fullBleed = location.pathname.startsWith('/pos') || location.pathname.startsWith('/barista/barra')

  return (
    <SidebarProvider {...marginDrag}>
      <CloseMobileSidebarOnNavigate />
      <Sidebar collapsible="icon" variant="inset">
        <SidebarHeader {...drag}>
          <Link to="/" className="flex items-center gap-2 px-2 py-1.5">
            <Logo className="size-8" />
            <div className="grid leading-tight group-data-[collapsible=icon]:hidden">
              <span className="font-heading text-base font-semibold">{BRAND.name}</span>
              <span className="text-xs text-muted-foreground">{BRAND.tagline}</span>
            </div>
          </Link>
        </SidebarHeader>
        <SidebarContent data-tour="sidebar">
          {groups.map((g, gi) => (
            <Fragment key={g.key}>
              {gi > 0 && <SidebarSeparator className="bg-sidebar-border/60" />}
              <SidebarGroup>
                <SidebarGroupLabel>{g.label}</SidebarGroupLabel>
                <SidebarGroupContent>
                  <SidebarMenu>
                    {g.items.map((item) => {
                      const active =
                        item.to === '/' ? location.pathname === '/' : location.pathname.startsWith(item.to)
                      return (
                        <SidebarMenuItem key={item.to}>
                          <SidebarMenuButton
                            asChild
                            isActive={active}
                            tooltip={item.label}
                            size="lg"
                            className="group-data-[collapsible=icon]:justify-center"
                          >
                            <NavLink to={item.to} data-tour={`nav-${item.to}`}>
                              <item.icon />
                              <span className="group-data-[collapsible=icon]:hidden">{item.label}</span>
                            </NavLink>
                          </SidebarMenuButton>
                          {item.feature && license.data && !hasFeature(license.data, item.feature) && (
                          <ProBadge className="ml-auto group-data-[collapsible=icon]:hidden" />
                        )}
                        {item.to === '/avisos' && !!alertSummary?.open && (
                            <SidebarMenuBadge>{alertSummary.open}</SidebarMenuBadge>
                          )}
                        </SidebarMenuItem>
                      )
                    })}
                  </SidebarMenu>
                </SidebarGroupContent>
              </SidebarGroup>
            </Fragment>
          ))}
        </SidebarContent>
        <SidebarFooter>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <SidebarMenuButton size="lg" data-tour="user">
                <Avatar className="size-8">
                  <AvatarFallback className={cn('text-xs font-semibold', AVATAR_COLORS[user.color])}>
                    {initials(user.name)}
                  </AvatarFallback>
                </Avatar>
                <div className="grid text-left leading-tight group-data-[collapsible=icon]:hidden">
                  <span className="truncate text-sm font-medium">{user.name}</span>
                  <span className="truncate text-xs text-muted-foreground">{ROLE_LABEL[user.role]}</span>
                </div>
              </SidebarMenuButton>
            </DropdownMenuTrigger>
            <DropdownMenuContent side="top" align="start" className="w-56">
              <DropdownMenuLabel>Tema</DropdownMenuLabel>
              <DropdownMenuItem onClick={() => setTheme('light')}>
                <Sun /> Claro {theme === 'light' && '✓'}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setTheme('dark')}>
                <Moon /> Oscuro {theme === 'dark' && '✓'}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setTheme('system')}>
                <Monitor /> Sistema {theme === 'system' && '✓'}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={tour.start}>
                <GraduationCap /> Ver tutorial
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => logout()}>
                <LogOut /> Cerrar sesión
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </SidebarFooter>
        <SidebarRail />
      </Sidebar>
      <SidebarInset className="min-w-0">
        <header
          className={cn(
            'sticky top-0 z-20 flex h-14 items-center gap-2 border-b bg-background/80 px-4 backdrop-blur select-none',
            desktop.api && 'pr-0',
          )}
          {...drag}
        >
          <SidebarTrigger />
          <button
            onClick={() => setPaletteOpen(true)}
            data-tour="search"
            className="ml-1 flex h-9 w-full max-w-sm items-center gap-2 rounded-lg border bg-muted/40 px-3 text-sm text-muted-foreground hover:bg-muted"
          >
            <Search className="size-4" />
            <span className="flex-1 text-left">Buscar o ir a…</span>
            <kbd className="hidden rounded border bg-background px-1.5 text-[10px] font-medium sm:inline">Ctrl K</kbd>
          </button>
          <div className="ml-auto flex items-center gap-1">
            <Button variant="ghost" size="icon" onClick={tour.start} aria-label="Ver tutorial" title="Ver tutorial">
              <CircleHelp />
            </Button>
            <Button variant="ghost" size="icon" asChild className="relative">
              <Link to="/avisos" aria-label="Alertas" data-tour="alerts">
                <Bell />
                {!!alertSummary?.open && (
                  <Badge
                    className={cn(
                      'absolute -top-1 -right-1 h-4 min-w-4 rounded-full px-1 text-[10px]',
                      alertSummary.critical ? 'bg-destructive text-white' : '',
                    )}
                  >
                    {alertSummary.open}
                  </Badge>
                )}
              </Link>
            </Button>
            <Button variant="ghost" size="icon" onClick={() => logout()} aria-label="Bloquear" data-tour="lock">
              <Lock />
            </Button>
            {desktop.api && <div className="mx-1 h-6 w-px bg-border" />}
            <WindowControls className="h-14" />
          </div>
        </header>
        <LicenseBanner />
        <main className={cn('flex-1', fullBleed ? 'p-0' : 'mx-auto w-full max-w-[1500px] p-4 md:p-6')}>
          <Outlet />
        </main>
      </SidebarInset>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </SidebarProvider>
  )
}
