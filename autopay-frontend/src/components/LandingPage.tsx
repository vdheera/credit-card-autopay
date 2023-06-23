import React from 'react';
import logo from '../logo.png'
import '../App.css';
import PlaidLink from './PlaidLink';


export const LandingPage = () => {

// when a user signs up, plaid link should be initialized & can just use one column account that i pay out of:
// ho

    return (
        <div>
            <header className="App-header">
                <img src={logo} className="App-logo" alt="logo" />
                <p>
                Improve your credit score by setting up autopay that automatically pays your credit card bill once you've spent 30% of your credit limit.
                </p>
                <button >
                Get started by linking your bank account below!
                </button>
            </header>
            <body>
                <PlaidLink />
            </body>
        </div>

    )
}