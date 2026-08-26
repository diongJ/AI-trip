import { useState } from 'react'
import { Menu } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from '@/components/ui/sheet'

const NAV_ITEMS = [
  { href: '#data', label: '数据可信' },
  { href: '#features', label: '核心功能' },
  { href: '#qa', label: '问答演示' },
  { href: '#graph', label: '图谱探索' },
  { href: '#pipeline', label: '方法流程' },
  { href: '#evaluation', label: '评测' },
]

/** Origin UI 风格导航栏：克制、清晰，移动端抽屉 */
export function Navbar() {
  const [open, setOpen] = useState(false)

  return (
    <header className="sticky top-0 z-50 border-b bg-background/90 backdrop-blur-sm">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
        <a href="#top" className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary font-serif-sc text-base font-bold text-primary-foreground">
            越
          </span>
          <span className="font-serif-sc text-sm font-semibold tracking-wide sm:text-base">
            南越王博物院 · 知识图谱与智慧导览
          </span>
        </a>

        <nav className="hidden items-center gap-1 md:flex">
          {NAV_ITEMS.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
            >
              {item.label}
            </a>
          ))}
          <Button asChild size="sm" className="ml-2">
            <a href="#qa">在线体验</a>
          </Button>
        </nav>

        <div className="md:hidden">
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="打开导航菜单">
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-64">
              <SheetTitle className="font-serif-sc">页面导航</SheetTitle>
              <nav className="mt-6 flex flex-col gap-1">
                {NAV_ITEMS.map((item) => (
                  <a
                    key={item.href}
                    href={item.href}
                    onClick={() => setOpen(false)}
                    className="rounded-md px-3 py-2.5 text-sm hover:bg-secondary"
                  >
                    {item.label}
                  </a>
                ))}
                <Button asChild className="mt-3">
                  <a href="#qa" onClick={() => setOpen(false)}>在线体验</a>
                </Button>
              </nav>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  )
}
