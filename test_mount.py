import asyncio
from textual.widgets import TabbedContent, TabPane, Static
from textual.app import App, ComposeResult

class TestApp(App):
    def compose(self) -> ComposeResult:
        with TabbedContent():
            with TabPane('A', id='a'):
                yield Static('Hello A')
            with TabPane('B', id='b'):
                yield Static('Hello B')

async def main():
    app = TestApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        print('SIMPLE MOUNT OK')

asyncio.run(main())
