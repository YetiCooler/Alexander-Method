load-pt-components:
	python3 -m commands.add_pt_components $(path)

pyinstaller:
	pyinstaller main.spec