```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>QuickClick</title>
    
    <style>
        /* --- CSS: Base Reset --- */
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: sans-serif;
            user-select: none;
            -webkit-user-select: none;
            -webkit-tap-highlight-color: transparent;
            touch-action: manipulation;
        }

        /* If the user holds the phone vertically before the code forces it,
           this ensures the background remains black and centered.
        */
        body {
            background-color: #000000; 
            color: #ffffff;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            width: 100vw;
            overflow: hidden;
        }

        #app-container {
            width: 100%;
            height: 100%;
            display: flex;
            position: relative;
        }

        /* Screen Management */
        .screen {
            display: none; 
            width: 100%;
            height: 100%;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            position: absolute;
            top: 0;
            left: 0;
        }

        .active-screen {
            display: flex; 
        }

        /* --- Menu Screen Styles --- */
        #menu-screen h1 {
            font-size: 4rem;
            margin-bottom: 30px;
            color: #ff3333;
            letter-spacing: 3px;
            text-shadow: 0 0 20px rgba(255, 0, 0, 0.5);
        }

        .menu-btn {
            background-color: #111;
            color: white;
            border: 2px solid #333;
            padding: 15px 40px;
            margin: 10px;
            font-size: 1.5rem;
            border-radius: 8px;
            width: 300px;
            cursor: pointer;
            transition: background-color 0.1s;
        }

        .menu-btn:active {
            background-color: #333;
            border-color: #ff3333;
        }

        .back-btn {
            position: absolute;
            top: 20px;
            left: 20px;
            background: none;
            border: none;
            color: #888;
            font-size: 1.2rem;
            cursor: pointer;
            z-index: 20;
        }

        /* --- Game Screen Styles --- */
        #score-display {
            position: absolute;
            top: 10%;
            font-size: 3.5rem;
            font-weight: bold;
            color: rgba(255, 255, 255, 0.9);
            text-shadow: 0 5px 15px rgba(0,0,0,1);
            z-index: 10;
            pointer-events: none;
        }

        /* --- THE MASSIVE, REALISTIC, STATIC BUTTON --- */
        #giant-btn {
            width: 80vw;
            height: 75vh;
            border-radius: 50%;
            border: none;
            outline: none;
            cursor: pointer;
            position: relative;
            
            background: radial-gradient(circle at 50% 30%, #ff1a1a 0%, #b30000 50%, #330000 100%);
            
            box-shadow: 
                0 0 0 12px #0a0a0a,          
                0 0 0 22px #000000,          
                inset 0 -40px 60px rgba(0, 0, 0, 0.9), 
                inset 0 15px 30px rgba(255, 255, 255, 0.3); 
        }

        #giant-btn::after {
            content: '';
            position: absolute;
            top: 6%;
            left: 25%;
            width: 50%;
            height: 25%;
            border-radius: 50%;
            background: linear-gradient(to bottom, rgba(255, 255, 255, 0.85) 0%, rgba(255, 255, 255, 0) 100%);
            pointer-events: none;
            filter: blur(1px); 
        }
           
    </style>
</head>
<body>

    <div id="app-container">

        <!-- SCREEN 1: Main Menu -->
        <div id="menu-screen" class="screen active-screen">
            <h1>QUICKCLICK</h1>
            <button class="menu-btn" onclick="startGame()">Start</button>
            <button class="menu-btn" onclick="loadGame()">Load Game</button>
            <button class="menu-btn" onclick="openSettings()">Settings</button>
        </div>

        <!-- SCREEN 2: The Game -->
        <div id="game-screen" class="screen">
            <button class="back-btn" onclick="goToMenu()">← Menu</button>
            <div id="score-display">0</div>
            <button id="giant-btn"></button>
        </div>

        <!-- SCREEN 3: Settings -->
        <div id="settings-screen" class="screen">
            <button class="back-btn" onclick="goToMenu()">← Menu</button>
            <h2 style="font-size: 3rem; margin-bottom: 30px;">Settings</h2>
            <p style="color: #888; font-size: 1.5rem;">(Themes and Preferences go here)</p>
        </div>

    </div>

    <script>
        /* --- JAVASCRIPT: Logic, Autosave, and Fullscreen Engine --- */
        
        let clicks = 0;
        const SAVE_KEY = "QUICKCLICK_SaveData"; 

        const menuScreen = document.getElementById('menu-screen');
        const gameScreen = document.getElementById('game-screen');
        const settingsScreen = document.getElementById('settings-screen');
        const scoreDisplay = document.getElementById('score-display');
        const giantBtn = document.getElementById('giant-btn');

        // --- FULLSCREEN & LANDSCAPE LOCK ---
        async function forceImmersiveMode() {
            try {
                // 1. Force Fullscreen (Hides status bar and nav bar)
                if (document.documentElement.requestFullscreen) {
                    await document.documentElement.requestFullscreen();
                } else if (document.documentElement.webkitRequestFullscreen) { // Safari/Old Webkit
                    await document.documentElement.webkitRequestFullscreen();
                }

                // 2. Force Landscape Mode
                if (screen.orientation && screen.orientation.lock) {
                    await screen.orientation.lock("landscape");
                }
            } catch (err) {
                console.log("Immersive mode blocked by browser. User must rotate manually.");
            }
        }

        // Screen Navigation
        function switchScreen(screenToShow) {
            menuScreen.classList.remove('active-screen');
            gameScreen.classList.remove('active-screen');
            settingsScreen.classList.remove('active-screen');
            screenToShow.classList.add('active-screen');
        }

        function goToMenu() {
            autoSave(); 
            switchScreen(menuScreen);
        }

        function openSettings() {
            switchScreen(settingsScreen);
        }

        // Gameplay triggers
        function startGame() {
            forceImmersiveMode(); // Forces screen turn and full screen!
            clicks = 0; 
            updateUI();
            switchScreen(gameScreen);
        }

        function registerClick() {
            clicks++;
            updateUI();
        }

        function updateUI() {
            scoreDisplay.innerText = clicks;
        }

        // Touch event to make it insanely fast on mobile
        giantBtn.addEventListener('touchstart', function(e) {
            e.preventDefault(); 
            registerClick();
        });
        
        giantBtn.addEventListener('mousedown', function(e) {
            if (e.pointerType === 'mouse') {
                registerClick();
            }
        });

        // Save & Load System
        function autoSave() {
            const saveData = { savedClicks: clicks };
            localStorage.setItem(SAVE_KEY, JSON.stringify(saveData));
        }

        function loadGame() {
            forceImmersiveMode(); // Forces screen turn and full screen!
            const savedDataString = localStorage.getItem(SAVE_KEY);
            if (savedDataString) {
                const parsedData = JSON.parse(savedDataString);
                clicks = parsedData.savedClicks || 0;
            } else {
                clicks = 0;
            }
            updateUI();
            switchScreen(gameScreen);
        }

        // Auto-save triggers
        window.addEventListener("beforeunload", autoSave);
        document.addEventListener("visibilitychange", () => {
            if (document.hidden) {
                autoSave();
            }
        });
    </script>
</body>
</html>


```
