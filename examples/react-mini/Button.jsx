import React from 'react';
import { Icon } from './Icon';

export function PrimaryButton({ variant = 'primary', size = 'md', icon, children }) {
  return <button className={`btn btn-${variant} btn-${size}`}>{icon ? <Icon name="check"/> : null}{children}</button>;
}

export function SecondaryButton(props) {
  return <button className="btn btn-secondary"><Icon name="x"/>{props.children}</button>;
}

export default function Button({ variant = 'primary', size = 'md', icon, children }) {
  return (
    <button className={`btn btn-${variant} btn-${size}`}>
      {icon ? <Icon name="star"/> : null}
      {children}
    </button>
  );
}
