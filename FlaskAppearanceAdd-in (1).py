import adsk.core, adsk.fusion, traceback, threading, json, urllib.request, time

FlaskURL = 'http://172.24.1.227:5000/get-value'

app = None
ui = None
stopPolling = False
pollThread = None
customEventId = 'FlaskUpdateEvent' # Corrected event ID to match registration

# Global event handler instance
onFlaskUpdate = None

def updateAppearanceFromValue(value):
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        rootComp = design.rootComponent
        allOccurrences = rootComp.allOccurrences

        # Choose appearance name based on threshold
        if value < 5.5:
            appearanceName = 'Paint - Enamel Glossy (Red)'
            #ui.messageBox(f"Value {value:.4f} → RED (1)")
        else:
            appearanceName = 'Paint - Enamel Glossy (Green)'
            #ui.messageBox(f"Value {value:.4f} → GREEN (0)")

        # Find the appearance in all libraries
        appearance = None
        for i in range(app.materialLibraries.count):
            library = app.materialLibraries.item(i)
            appearance = library.appearances.itemByName(appearanceName)
            if appearance:
                break

        if not appearance:
            ui.messageBox(f"Could not find appearance '{appearanceName}' in any library.")
            return

        # Apply appearance to all visible bodies
        for occ in allOccurrences:
            bodies = occ.bRepBodies
            for body in bodies:
                if body.isVisible:
                    body.appearance = appearance

    except:
        if ui:
            ui.messageBox('Failed to update appearance:\n{}'.format(traceback.format_exc()))


class FlaskUpdateEventHandler(adsk.core.CustomEventHandler):
    def notify(self, args):
        try:
            eventArgs = adsk.core.CustomEventArgs.cast(args)
            value = float(eventArgs.additionalInfo)
            updateAppearanceFromValue(value)

            # 🖼️ Force graphics update
            app = adsk.core.Application.get()
            app.activeViewport.refresh()

        except:
            app = adsk.core.Application.get()
            ui = app.userInterface
            ui.messageBox('Failed in FlaskUpdateEventHandler:\n{}'.format(traceback.format_exc()))


def pollFlaskServerThread():
    def poll():
        app = adsk.core.Application.get()
        while not stopPolling: # Use the stopPolling flag
            try:
                url = FlaskURL
                response = urllib.request.urlopen(url, timeout=2)
                result = json.loads(response.read())
                value = result['value']

                # Fire custom event with the new value
                app.fireCustomEvent(customEventId, str(value)) # Use the customEventId variable

            except Exception as e:
                print(f"Polling error: {e}")

            time.sleep(2.5)  # Poll every 2.5 seconds

    # Start thread
    thread = threading.Thread(target=poll)
    thread.daemon = True
    thread.start()


def run(context):
    global app, ui, onFlaskUpdate, pollThread
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        # Create an instance of the event handler
        onFlaskUpdate = FlaskUpdateEventHandler()

        # Register the custom event
        app.registerCustomEvent(customEventId)

        # Add the handler to the custom event
        app.registerCustomEvent(customEventId).add(onFlaskUpdate)

        # Get initial value
        try:
            url = FlaskURL
            response = urllib.request.urlopen(url, timeout=2)
            result = json.loads(response.read())
            initial_value = result['value']
            updateAppearanceFromValue(initial_value)
        except Exception as e:
            ui.messageBox(f"Error getting initial value: {e}")

        # Start polling in background
        pollThread = pollFlaskServerThread()

    except:
        if ui:
            ui.messageBox('Failed in run:\n{}'.format(traceback.format_exc()))


def stop(context):
    global stopPolling, pollThread
    stopPolling = True
    if pollThread and pollThread.is_alive():
        pollThread.join(timeout=5) # Wait for the thread to finish (with a timeout)
    app = adsk.core.Application.get()
    if app:
        app.unregisterCustomEvent(customEventId)