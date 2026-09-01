import asyncio
from textual.widgets import TabbedContent, TabPane, Static, Header, Footer
from textual.app import App, ComposeResult

class TestApp(App):
    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane('Overview', id='overview'):
                with TabbedContent():
                    with TabPane('Dashboard', id='overview-dashboard'):
                        yield Static('Dashboard')
                    with TabPane('Profiles', id='overview-profiles'):
                        yield Static('Profiles')
            with TabPane('Endpoint & Keys', id='endpoint-keys'):
                with TabbedContent():
                    with TabPane('Endpoints', id='ek-endpoints'):
                        yield Static('Endpoints')
                    with TabPane('Keys', id='ek-keys'):
                        yield Static('Keys')
            with TabPane('Providers', id='providers'):
                with TabbedContent():
                    with TabPane('Manage', id='providers-manage'):
                        yield Static('Manage')
                    with TabPane('Models', id='providers-models'):
                        yield Static('Models')
            with TabPane('Nodes', id='nodes'):
                yield Static('Nodes')
        yield Footer()

async def main():
    app = TestApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        tabs = app.query('TabPane')
        print('TABS:', [t.id for t in tabs])
        print('MOUNTED OK')

asyncio.run(main())
