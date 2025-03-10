import React from "react";
import ReactDOM from "react-dom";

import { GlobalContextProvider } from "./components/GlobalContext";
import App from "./App";

import "./index.css";

ReactDOM.render(
    <GlobalContextProvider>
        <App />
    </GlobalContextProvider>,
    document.getElementById("root")
);

// import reportWebVitals from './reportWebVitals';
// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
// reportWebVitals();
